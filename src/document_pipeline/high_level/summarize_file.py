from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from time import perf_counter
from typing import Any, Callable

from src.document_pipeline.mid_level import ExtractionContext, build_doc_map, extract_single_doc
from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, SelectedEvidence

from .generate_report import ReportLLMClient
from .markdown_format import sentence_per_line_markdown
from .select_evidence import format_selected_evidence, select_evidence_blocks
from .write_output_plan import SUMMARY_SUBSECTIONS, write_output_plan

ProgressCallback = Callable[[str, str], None]

DEFAULT_FILE_SUMMARY_GOAL = "Summarize this file as a concise engineering summary."


@dataclass(frozen=True)
class SummarizeFileResult:
    document: ExtractedDocument
    doc_map: DocumentMap
    output_plan: OutputPlan
    selected_evidence: SelectedEvidence
    markdown: str
    used_llm: bool = False
    fallback_reason: str = ""
    timings: dict[str, float] = field(default_factory=dict)
    saved_files: list[Path] = field(default_factory=list)


def summarize_file_pipeline(
    working_folder: Path,
    file_path: Path,
    goal: str = DEFAULT_FILE_SUMMARY_GOAL,
    llm_client: ReportLLMClient | None = None,
    llm_input_chars: int = 12000,
    progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> SummarizeFileResult:
    """Extract and summarize one source file without touching folder-level report artifacts."""

    root = working_folder.expanduser().resolve()
    source_path = file_path.expanduser().resolve()
    query = goal.strip() or DEFAULT_FILE_SUMMARY_GOAL
    total_started = perf_counter()
    timings: dict[str, float] = {}

    _check_cancelled(cancel_event)
    _emit(progress, "status", "[1/6] Extracting selected file...\n")
    started = perf_counter()
    document = extract_single_doc(source_path, ExtractionContext(working_folder=root))
    timings["extraction"] = _elapsed(started)
    _emit(progress, "status", f"Extracted {document.source.filename} in {_format_seconds(timings['extraction'])}.\n")

    _check_cancelled(cancel_event)
    _emit(progress, "status", "[2/6] Building document map...\n")
    started = perf_counter()
    doc_map = build_doc_map([document])
    timings["mapping"] = _elapsed(started)
    _emit(progress, "status", f"Mapped {len(doc_map.blocks)} block(s) in {_format_seconds(timings['mapping'])}.\n")

    _check_cancelled(cancel_event)
    _emit(progress, "status", "[3/6] Writing file summary plan...\n")
    started = perf_counter()
    output_plan = write_output_plan([document], doc_map, goal=query)
    timings["planning"] = _elapsed(started)
    _emit(progress, "status", f"Created {len(output_plan.sections)} section(s) in {_format_seconds(timings['planning'])}.\n")

    _check_cancelled(cancel_event)
    _emit(progress, "status", "[4/6] Selecting file evidence...\n")
    started = perf_counter()
    selected_evidence = select_evidence_blocks([document], output_plan, query, llm_input_chars)
    timings["evidence_selection"] = _elapsed(started)
    _emit(
        progress,
        "status",
        f"Selected {len(selected_evidence.blocks)} evidence block(s) in {_format_seconds(timings['evidence_selection'])}.\n",
    )

    _check_cancelled(cancel_event)
    _emit(progress, "status", "[5/6] Generating file summary...\n")
    started = perf_counter()
    markdown, used_llm, fallback_reason, attempts = _generate_file_summary(
        output_plan=output_plan,
        document=document,
        selected_evidence=selected_evidence,
        llm_client=llm_client,
        query=query,
        max_input_chars=llm_input_chars,
        progress=progress,
        cancel_event=cancel_event,
    )
    timings["llm_generation"] = _elapsed(started)

    _check_cancelled(cancel_event)
    _emit(progress, "status", "[6/6] Saving file summary artifacts...\n")
    started = perf_counter()
    saved_files = _save_file_summary_artifacts(
        root=root,
        document=document,
        doc_map=doc_map,
        output_plan=output_plan,
        selected_evidence=selected_evidence,
        attempts=attempts,
        markdown=markdown,
    )
    timings["saving"] = _elapsed(started)
    timings["total"] = _elapsed(total_started)
    _emit(progress, "status", f"Saved {len(saved_files)} artifact(s) in {_format_seconds(timings['saving'])}.\n")
    _emit(progress, "status", _format_timings(timings))

    return SummarizeFileResult(
        document=document,
        doc_map=doc_map,
        output_plan=output_plan,
        selected_evidence=selected_evidence,
        markdown=markdown,
        used_llm=used_llm,
        fallback_reason=fallback_reason,
        timings=timings,
        saved_files=saved_files,
    )


def _generate_file_summary(
    *,
    output_plan: OutputPlan,
    document: ExtractedDocument,
    selected_evidence: SelectedEvidence,
    llm_client: ReportLLMClient | None,
    query: str,
    max_input_chars: int,
    progress: ProgressCallback | None,
    cancel_event: Event | None,
) -> tuple[str, bool, str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    if llm_client is None:
        markdown = _fallback_file_summary(output_plan, document, selected_evidence)
        _emit(progress, "status", "LLM client is not configured. Using deterministic file summary.\n")
        _emit(progress, "markdown", markdown)
        attempts.append({"stage": "file_summary", "status": "fallback", "error": "LLM client is not configured."})
        return markdown, False, "LLM client is not configured.", attempts

    try:
        prompt = _file_summary_prompt(output_plan, document, selected_evidence, query, max_input_chars)
        messages = [
            {
                "role": "system",
                "content": (
                    "You write concise single-file engineering summaries from extracted evidence. "
                    "Return Markdown only. Do not invent unsupported facts. Cite block IDs and the source filename."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        stream_chat_completion = getattr(llm_client, "stream_chat_completion", None)
        if callable(stream_chat_completion):
            parts: list[str] = []
            for chunk in stream_chat_completion(messages):
                _check_cancelled(cancel_event)
                if getattr(chunk, "kind", "") != "final":
                    continue
                text = getattr(chunk, "text", "")
                if not text:
                    continue
                parts.append(text)
                _emit(progress, "markdown", text)
            content = "".join(parts)
        else:
            content = llm_client.chat_completion(messages)
            _emit(progress, "markdown", content)
        markdown = content.strip()
        if not markdown:
            raise ValueError("File summary response was empty.")
        if not markdown.startswith("#"):
            markdown = f"# File Summary: {document.source.filename}\n\n{markdown}"
        markdown = sentence_per_line_markdown(markdown)
        attempts.append(
            {
                "stage": "file_summary",
                "status": "succeeded",
                "selected_evidence_block_count": len(selected_evidence.blocks),
                "llm_calls": 1,
            }
        )
        return markdown, True, "", attempts
    except Exception as exc:
        markdown = _fallback_file_summary(output_plan, document, selected_evidence)
        _emit(progress, "status", f"File summary LLM failed. Using deterministic fallback: {exc}\n")
        _emit(progress, "markdown", markdown)
        attempts.append({"stage": "file_summary", "status": "fallback", "error": str(exc)})
        return markdown, False, str(exc), attempts


def _file_summary_prompt(
    output_plan: OutputPlan,
    document: ExtractedDocument,
    selected_evidence: SelectedEvidence,
    query: str,
    max_input_chars: int,
) -> str:
    payload = {
        "summary_query": query,
        "output_plan": output_plan.to_dict(),
        "source_file": {
            "document_id": document.document_id,
            "filename": document.source.filename,
            "extension": document.source.extension,
            "blocks": len(document.blocks),
            "assets": len(document.assets),
        },
        "selected_evidence_block_count": len(selected_evidence.blocks),
        "selected_evidence": format_selected_evidence(selected_evidence),
    }
    summary_subsections = ", ".join(SUMMARY_SUBSECTIONS)
    return (
        "Write a single-file engineering summary as Markdown only.\n\n"
        "Requirements:\n"
        "- Start with exactly one H1 title in the form: File Summary: <filename>.\n"
        "- Use exactly these H2 sections in this order: Summary, Source Details, Open Issues and Next Actions.\n"
        f"- Under Summary, use H3 subsections when evidence supports them: {summary_subsections}.\n"
        "- If a Summary subsection lacks evidence, state the gap briefly instead of inventing content.\n"
        "- Use only the selected evidence packet from this one file.\n"
        "- In Source Details, include a compact table for filename, type, blocks, and assets.\n"
        "- Cite source filename and block ID for concrete claims.\n"
        "- Write each sentence on its own line in normal paragraphs.\n"
        "- Do not add extra H2 sections.\n\n"
        f"Grounded file-summary material:\n{_truncate(json.dumps(payload, ensure_ascii=False, indent=2), max_input_chars)}"
    )


def _fallback_file_summary(
    output_plan: OutputPlan,
    document: ExtractedDocument,
    selected_evidence: SelectedEvidence,
) -> str:
    lines = [f"# File Summary: {document.source.filename}", "", "## Summary", ""]
    blocks = selected_evidence.blocks
    for heading in SUMMARY_SUBSECTIONS:
        lines.extend([f"### {heading}", ""])
        matching = _fallback_entries_for_heading(heading, blocks)
        if matching:
            lines.extend(matching[:4])
        else:
            lines.append("- Evidence is not available for this subsection.")
        lines.append("")
    lines.extend(
        [
            "## Source Details",
            "",
            "| Source | Type | Blocks | Assets |",
            "|---|---:|---:|---:|",
            f"| {document.source.filename} | {document.source.extension} | {len(document.blocks)} | {len(document.assets)} |",
            "",
            "## Open Issues and Next Actions",
            "",
        ]
    )
    if document.warnings:
        lines.extend(f"- {warning}" for warning in document.warnings)
    else:
        lines.append("- Review cited evidence before using this file summary externally.")
        lines.append("- Verify assumptions, calculations, and recommendations against the source file.")
    lines.append("")
    return sentence_per_line_markdown("\n".join(lines))


def _fallback_entries_for_heading(heading: str, blocks) -> list[str]:
    entries: list[str] = []
    for block in blocks:
        text = " ".join(block.text.split())
        if not text:
            continue
        source = f"{block.source_filename} / {block.block_id}".strip(" /")
        if heading == "Quantitative Results" and not any(char.isdigit() for char in text):
            continue
        entries.append(f"- {_truncate(text, 320)} (`{source}`)")
    return entries


def _save_file_summary_artifacts(
    *,
    root: Path,
    document: ExtractedDocument,
    doc_map: DocumentMap,
    output_plan: OutputPlan,
    selected_evidence: SelectedEvidence,
    attempts: list[dict[str, Any]],
    markdown: str,
) -> list[Path]:
    output_dir = root / "llm_result" / "document_pipeline" / "file_summaries" / document.document_id
    output_dir.mkdir(parents=True, exist_ok=True)
    files = [
        _write_json(output_dir / "extracted_document.json", document.to_dict()),
        _write_json(output_dir / "document_map.json", doc_map.to_dict()),
        _write_json(output_dir / "output_plan.json", output_plan.to_dict()),
        _write_json(output_dir / "selected_evidence.json", selected_evidence.to_dict()),
        _write_json(output_dir / "summary_attempts.json", {"attempts": attempts}),
    ]
    summary_path = output_dir / "generated_summary.md"
    summary_path.write_text(markdown, encoding="utf-8")
    files.append(summary_path)
    return files


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def _emit(progress: ProgressCallback | None, kind: str, text: str) -> None:
    if progress is not None and text:
        progress(kind, text)


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Slash tool cancelled.")


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


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
