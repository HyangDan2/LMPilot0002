from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from time import perf_counter
from typing import Callable

from app.ingestion.scanner import scan_supported_files

from src.document_pipeline.mid_level import ExtractionContext, build_doc_map, extract_single_doc
from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, SelectedEvidence
from src.document_pipeline.storage import (
    load_extracted_documents,
    load_manifest_payload,
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
    extraction_cache_used: bool = False
    timings: dict[str, float] = field(default_factory=dict)
    prerequisite_steps: list[str] = field(default_factory=list)
    saved_files: list[Path] = field(default_factory=list)


def generate_report_pipeline(
    working_folder: Path,
    goal: str = DEFAULT_REPORT_GOAL,
    llm_client: ReportLLMClient | None = None,
    llm_input_chars: int = 12000,
    force_refresh: bool = False,
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
    total_started = perf_counter()
    timings: dict[str, float] = {}
    _check_cancelled(cancel_event)
    _emit(progress, "status", "[1/6] Extracting documents...\n")
    started = perf_counter()
    documents, extraction_cache_used = _load_or_extract_documents(root, force_refresh, progress, cancel_event)
    timings["extraction"] = _elapsed(started)
    _check_cancelled(cancel_event)
    cache_note = " from cache" if extraction_cache_used else ""
    _emit(progress, "status", f"Extracted {len(documents)} document(s){cache_note} in {_format_seconds(timings['extraction'])}.\n")
    _emit(progress, "status", "[2/6] Building document map...\n")
    started = perf_counter()
    doc_map = build_doc_map(documents)
    timings["mapping"] = _elapsed(started)
    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Mapped {len(doc_map.blocks)} block(s) in {_format_seconds(timings['mapping'])}.\n")
    _emit(progress, "status", "[3/6] Writing output plan...\n")
    started = perf_counter()
    output_plan = write_output_plan(documents, doc_map, goal=goal)
    timings["planning"] = _elapsed(started)
    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Created {len(output_plan.sections)} output-plan section(s) in {_format_seconds(timings['planning'])}.\n")
    _emit(progress, "status", "[4/6] Selecting compact evidence blocks...\n")
    started = perf_counter()
    selected_evidence = select_evidence_blocks(documents, output_plan, goal, llm_input_chars)
    timings["evidence_selection"] = _elapsed(started)
    _emit(
        progress,
        "status",
        f"Selected {len(selected_evidence.blocks)} evidence block(s) in {_format_seconds(timings['evidence_selection'])}.\n",
    )
    _check_cancelled(cancel_event)
    _emit(progress, "status", "[5/6] Generating final reasoned Markdown report...\n")
    started = perf_counter()
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
    timings["llm_generation"] = _elapsed(started)
    _check_cancelled(cancel_event)
    _emit(progress, "status", "[6/6] Saving report artifacts...\n")
    started = perf_counter()
    saved_files = [
        save_extracted_documents(root, documents),
        save_manifest(root, documents),
        save_document_map(root, doc_map),
        save_output_plan(root, output_plan),
        save_selected_evidence(root, selected_evidence),
        save_report_attempts(root, report.attempts),
        save_generated_markdown(root, report.markdown),
    ]
    timings["saving"] = _elapsed(started)
    timings["total"] = _elapsed(total_started)
    _emit(progress, "status", f"Saved {len(saved_files)} artifact(s) in {_format_seconds(timings['saving'])}.\n")
    _emit(progress, "status", _format_timings(timings))
    return GenerateReportResult(
        documents=documents,
        doc_map=doc_map,
        output_plan=output_plan,
        selected_evidence=selected_evidence,
        markdown=report.markdown,
        used_llm=report.used_llm,
        fallback_reason=report.fallback_reason,
        extraction_cache_used=extraction_cache_used,
        timings=timings,
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


def _load_or_extract_documents(
    root: Path,
    force_refresh: bool,
    progress: ProgressCallback | None,
    cancel_event: Event | None,
) -> tuple[list[ExtractedDocument], bool]:
    files = scan_supported_files(root)
    _emit(progress, "status", f"Found {len(files)} supported source file(s).\n")
    if not force_refresh:
        cached = _load_cached_documents(root, files)
        if cached is not None:
            _emit(progress, "status", "Reusing unchanged extracted_documents.json.\n")
            return cached, True

    context = ExtractionContext(working_folder=root)
    documents: list[ExtractedDocument] = []
    for path in files:
        _check_cancelled(cancel_event)
        documents.append(extract_single_doc(path, context))
    return documents, False


def _load_cached_documents(root: Path, files: list[Path]) -> list[ExtractedDocument] | None:
    try:
        manifest = load_manifest_payload(root)
        documents = load_extracted_documents(root)
    except (FileNotFoundError, OSError, ValueError):
        return None
    if not _manifest_matches_files(manifest, files):
        return None
    return documents


def _manifest_matches_files(manifest: dict, files: list[Path]) -> bool:
    entries = manifest.get("documents")
    if not isinstance(entries, list):
        return False
    if len(entries) != len(files):
        return False
    by_path: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        path_value = entry.get("path")
        if not isinstance(path_value, str):
            return False
        by_path[str(Path(path_value).expanduser().resolve())] = entry
    for path in files:
        resolved = str(path.expanduser().resolve())
        entry = by_path.get(resolved)
        if entry is None:
            return False
        try:
            stat = path.stat()
        except OSError:
            return False
        if entry.get("size_bytes") != stat.st_size:
            return False
        if entry.get("mtime_ns") != stat.st_mtime_ns:
            return False
    return True


def _elapsed(started: float) -> float:
    return perf_counter() - started


def _format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def _format_timings(timings: dict[str, float]) -> str:
    labels = [
        ("extraction", "extraction"),
        ("mapping", "mapping"),
        ("planning", "planning"),
        ("evidence_selection", "evidence selection"),
        ("llm_generation", "LLM generation"),
        ("saving", "saving"),
        ("total", "total"),
    ]
    lines = ["Timings:"]
    lines.extend(f"- {label}: {_format_seconds(timings.get(key, 0.0))}" for key, label in labels)
    return "\n".join(lines) + "\n"
