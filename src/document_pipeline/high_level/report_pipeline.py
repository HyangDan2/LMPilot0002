from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable

from src.document_pipeline.mid_level import ExtractionContext, build_doc_map, extract_docs
from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, SelectedEvidence
from src.document_pipeline.storage import (
    save_document_map,
    save_extracted_documents,
    save_generated_markdown,
    save_manifest,
    save_output_plan,
    save_report_attempts,
    save_selected_evidence,
)

from .generate_report import ReportLLMClient, generate_report
from .select_evidence import select_evidence_blocks
from .write_output_plan import DEFAULT_REPORT_GOAL, write_output_plan

ProgressCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class GenerateReportResult:
    documents: list[ExtractedDocument]
    doc_map: DocumentMap
    output_plan: OutputPlan
    selected_evidence: SelectedEvidence
    markdown: str
    used_llm: bool = False
    fallback_reason: str = ""
    prerequisite_steps: list[str] = field(default_factory=list)
    saved_files: list[Path] = field(default_factory=list)


def generate_report_pipeline(
    working_folder: Path,
    goal: str = DEFAULT_REPORT_GOAL,
    llm_client: ReportLLMClient | None = None,
    llm_input_chars: int = 12000,
    progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> GenerateReportResult:
    """Run the full report pipeline from source files and save every artifact.

    This function intentionally does not depend on slash-tool context state. It
    always extracts documents, builds a map, writes an output plan, selects
    evidence blocks, and then generates the final report from the attached
    folder.
    """

    root = working_folder.expanduser().resolve()
    _check_cancelled(cancel_event)
    _emit(progress, "status", "[1/5] Extracting documents...\n")
    documents = extract_docs(root, ExtractionContext(working_folder=root))
    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Extracted {len(documents)} document(s).\n")
    _emit(progress, "status", "[2/5] Building document map...\n")
    doc_map = build_doc_map(documents)
    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Mapped {len(doc_map.blocks)} block(s).\n")
    _emit(progress, "status", "[3/5] Writing output plan...\n")
    output_plan = write_output_plan(documents, doc_map, goal=goal)
    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Created {len(output_plan.sections)} output-plan section(s).\n")
    _emit(progress, "status", "[4/5] Selecting compact evidence blocks...\n")
    selected_evidence = select_evidence_blocks(documents, output_plan, goal, llm_input_chars)
    _emit(progress, "status", f"Selected {len(selected_evidence.blocks)} evidence block(s).\n")
    _check_cancelled(cancel_event)
    _emit(progress, "status", "[5/5] Generating final reasoned Markdown report...\n")
    report = generate_report(
        output_plan,
        documents,
        doc_map,
        selected_evidence,
        llm_client=llm_client,
        report_query=goal,
        max_input_chars=llm_input_chars,
        progress=progress,
        cancel_event=cancel_event,
    )
    _check_cancelled(cancel_event)
    _emit(progress, "status", "[6/6] Saving report artifacts...\n")
    saved_files = [
        save_extracted_documents(root, documents),
        save_manifest(root, documents),
        save_document_map(root, doc_map),
        save_output_plan(root, output_plan),
        save_selected_evidence(root, selected_evidence),
        save_report_attempts(root, report.attempts),
        save_generated_markdown(root, report.markdown),
    ]
    _emit(progress, "status", f"Saved {len(saved_files)} artifact(s).\n")
    return GenerateReportResult(
        documents=documents,
        doc_map=doc_map,
        output_plan=output_plan,
        selected_evidence=selected_evidence,
        markdown=report.markdown,
        used_llm=report.used_llm,
        fallback_reason=report.fallback_reason,
        prerequisite_steps=[
            "extract_docs",
            "build_doc_map",
            "write_output_plan",
            "select_evidence_blocks",
            "generate_report",
        ],
        saved_files=saved_files,
    )


def _emit(progress: ProgressCallback | None, kind: str, text: str) -> None:
    if progress is not None and text:
        progress(kind, text)


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Slash tool cancelled.")
