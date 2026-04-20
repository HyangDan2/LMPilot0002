from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.document_pipeline.mid_level import ExtractionContext, build_doc_map, chunk_sections, extract_docs
from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument, OutputPlan
from src.document_pipeline.storage import (
    save_chunk_summaries,
    save_chunks,
    save_document_map,
    save_extracted_documents,
    save_generated_markdown,
    save_manifest,
    save_output_plan,
    save_report_attempts,
    save_section_summaries,
)

from .generate_report import ReportLLMClient, generate_report
from .write_output_plan import DEFAULT_REPORT_GOAL, write_output_plan


@dataclass(frozen=True)
class GenerateReportResult:
    documents: list[ExtractedDocument]
    doc_map: DocumentMap
    chunks: list[EvidenceChunk]
    output_plan: OutputPlan
    markdown: str
    used_llm: bool = False
    fallback_reason: str = ""
    prerequisite_steps: list[str] = field(default_factory=list)
    saved_files: list[Path] = field(default_factory=list)


def generate_report_pipeline(
    working_folder: Path,
    goal: str = DEFAULT_REPORT_GOAL,
    max_chunk_chars: int = 2400,
    llm_client: ReportLLMClient | None = None,
    llm_input_chars: int = 12000,
) -> GenerateReportResult:
    """Run the full report pipeline from source files and save every artifact.

    This function intentionally does not depend on slash-tool context state. It
    always extracts documents, builds a map, chunks evidence, writes an output
    plan, and then generates the final report from the attached folder.
    """

    root = working_folder.expanduser().resolve()
    documents = extract_docs(root, ExtractionContext(working_folder=root))
    doc_map = build_doc_map(documents)
    chunks = chunk_sections(documents, max_chars=max_chunk_chars)
    output_plan = write_output_plan(documents, doc_map, chunks, goal=goal)
    report = generate_report(
        output_plan,
        documents,
        doc_map,
        chunks,
        llm_client=llm_client,
        report_query=goal,
        max_input_chars=llm_input_chars,
    )
    saved_files = [
        save_extracted_documents(root, documents),
        save_manifest(root, documents),
        save_document_map(root, doc_map),
        save_chunks(root, chunks),
        save_output_plan(root, output_plan),
        save_chunk_summaries(root, report.chunk_summaries),
        save_section_summaries(root, report.section_summaries),
        save_report_attempts(root, report.attempts),
        save_generated_markdown(root, report.markdown),
    ]
    return GenerateReportResult(
        documents=documents,
        doc_map=doc_map,
        chunks=chunks,
        output_plan=output_plan,
        markdown=report.markdown,
        used_llm=report.used_llm,
        fallback_reason=report.fallback_reason,
        prerequisite_steps=[
            "extract_docs",
            "build_doc_map",
            "chunk_sections",
            "write_output_plan",
            "generate_report",
        ],
        saved_files=saved_files,
    )
