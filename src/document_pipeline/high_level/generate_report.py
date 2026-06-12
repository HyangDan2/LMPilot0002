from __future__ import annotations

from threading import Event
from typing import Any, Callable, Protocol

from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, LLMReportResult, OutputPlan, SelectedEvidence

from .generate_output_plan import generate_output_plan
from .markdown_format import sentence_per_line_markdown
from .select_evidence import format_selected_evidence
<<<<<<< HEAD
from .write_output_plan import SUMMARY_SUBSECTIONS
=======
from .write_output_plan import REPORT_SECTION_TITLES
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3

ProgressCallback = Callable[[str, str], None]


class ReportLLMClient(Protocol):
    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        ...


def generate_report(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    doc_map: DocumentMap,
    selected_evidence: SelectedEvidence,
    llm_client: ReportLLMClient | None,
    report_query: str = "",
    max_input_chars: int = 12000,
    recursive_summary: str = "",
    progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> LLMReportResult:
    """Generate final markdown from representative evidence and optional grouped context."""

    query = report_query.strip() or output_plan.goal
    attempts: list[dict[str, Any]] = []
    _check_cancelled(cancel_event)
    if llm_client is None:
        _emit(progress, "status", "LLM client is not configured. Using deterministic fallback report.\n")
        markdown = sentence_per_line_markdown(generate_output_plan(output_plan, documents, doc_map, selected_evidence))
        _emit(progress, "markdown", markdown)
        return LLMReportResult(
            markdown=markdown,
            attempts=[{"stage": "final_report", "status": "fallback", "error": "LLM client is not configured."}],
            used_llm=False,
            fallback_reason="LLM client is not configured.",
        )

    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Using {len(selected_evidence.blocks)} selected evidence block(s) for the final LLM prompt.\n")
    try:
        markdown = _write_final_markdown(
            llm_client=llm_client,
            output_plan=output_plan,
            documents=documents,
            selected_evidence=selected_evidence,
            query=query,
            max_input_chars=max_input_chars,
            recursive_summary=recursive_summary,
            attempts=attempts,
            progress=progress,
            cancel_event=cancel_event,
        )
        return LLMReportResult(
            markdown=markdown,
            attempts=attempts,
            used_llm=True,
        )
    except Exception as exc:
        markdown = sentence_per_line_markdown(generate_output_plan(output_plan, documents, doc_map, selected_evidence))
        _emit(progress, "status", f"Final LLM report failed. Using deterministic fallback: {exc}\n")
        _emit(progress, "markdown", markdown)
        attempts.append({"stage": "final_report", "status": "fallback", "error": str(exc)})
        return LLMReportResult(
            markdown=markdown,
            attempts=attempts,
            used_llm=False,
            fallback_reason=str(exc),
        )


def _write_final_markdown(
    *,
    llm_client: ReportLLMClient,
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    selected_evidence: SelectedEvidence,
    query: str,
    max_input_chars: int,
    recursive_summary: str,
    attempts: list[dict[str, Any]],
    progress: ProgressCallback | None,
    cancel_event: Event | None,
) -> str:
    _check_cancelled(cancel_event)
    prompt = final_markdown_prompt(output_plan, documents, selected_evidence, query, max_input_chars, recursive_summary)
    messages = [
        {
            "role": "system",
            "content": (
                "You write concise engineering reports from extracted evidence. "
                "Return Markdown only. Do not invent unsupported facts. Cite block IDs and source filenames."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    _emit(progress, "status", "Generating final Markdown report with one LLM call...\n")
    _check_cancelled(cancel_event)
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
        _check_cancelled(cancel_event)
        _emit(progress, "markdown", content)
    markdown = content.strip()
    if not markdown:
        raise ValueError("Final report response was empty.")
    if not markdown.startswith("#"):
        markdown = f"# {output_plan.title}\n\n{markdown}"
    markdown = sentence_per_line_markdown(markdown)
    attempts.append(
        {
            "stage": "final_report",
            "status": "succeeded",
            "selected_evidence_block_count": len(selected_evidence.blocks),
            "final_prompt_chars": len(prompt),
            "grouped_evidence_context_chars": len(recursive_summary),
            "llm_calls": 1,
        }
    )
    _emit(progress, "status", "\nFinal Markdown report generated.\n")
    return markdown.rstrip() + "\n"


def final_markdown_prompt(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    selected_evidence: SelectedEvidence,
    query: str,
    max_input_chars: int,
    recursive_summary: str = "",
) -> str:
    sources = "\n".join(
        f"- {document.source.filename} ({document.source.extension}): "
        f"{len(document.blocks)} block(s), {len(document.assets)} asset(s), document_id={document.document_id}"
        for document in documents
    ) or "- none"
<<<<<<< HEAD
    summary_subsections = ", ".join(SUMMARY_SUBSECTIONS)
=======
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    instructions = (
        "Write the final report as Markdown only, using a concise engineering-report tone.\n\n"
        "Requirements:\n"
        "- Start with exactly one H1 title.\n"
<<<<<<< HEAD
        "- Use exactly these H2 sections in this order: Summary, Source Documents, Open Issues and Next Actions.\n"
        f"- Under Summary, use H3 subsections when evidence supports them: {summary_subsections}.\n"
        "- If a Summary subsection lacks evidence, write: Not explicitly stated in the selected evidence.\n"
        "- Focus on the report query.\n"
        "- Use only the selected evidence packet.\n"
        "- In Summary, summarize only what the evidence explicitly states.\n"
        "- Do not infer architecture, databases, proprietary engines, implementation details, risks, constraints, or recommendations unless explicitly stated in cited evidence.\n"
        "- Do not add recommendations unless the selected evidence itself contains recommendations or requested next actions.\n"
        "- In Source Documents, include a compact traceability table for the source files.\n"
        "- In Open Issues and Next Actions, list only extraction warnings, missing selected evidence, or explicitly stated unresolved items.\n"
        "- Distinguish explicit facts from unstated items and gaps.\n"
        "- Include quantitative values only when evidence contains numbers, tests, specs, or results.\n"
=======
        f"- Use exactly these H2 sections in this order: {', '.join(REPORT_SECTION_TITLES)}.\n"
        "- Focus on the report query.\n"
        "- Use only the selected evidence packet plus the provided grouped-evidence context when present.\n"
        "- Keep the approximate emphasis of the report as: Summary about 10%, Key Concepts about 50%, Open Questions about 10%, Next Actions about 10%, Related Documents about 10%.\n"
        "- Summary should be brief and orient the reader quickly.\n"
        "- Key Concepts should dominate the report and explain the document content in an engineering sense.\n"
        "- In Key Concepts, include every important concept supported by the documents, even if some concepts are small or appear only once.\n"
        "- Merge duplicate concepts, but do not omit meaningful ones.\n"
        "- Open Questions should identify ambiguities, missing evidence, assumptions that still need confirmation, and parser or extraction gaps when relevant.\n"
        "- Next Actions should list practical engineering follow-up work, validation checks, decisions, or investigations suggested by the evidence.\n"
        "- Related Documents should list the source files and briefly explain why each one matters to the report topic.\n"
        "- Ground all factual claims in the evidence and avoid unsupported invention.\n"
        "- Include quantitative values when evidence contains numbers, tests, specs, or results.\n"
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
        "- Cite source filename and block ID for concrete claims.\n"
        "- Write each sentence on its own line in normal paragraphs.\n"
        "- Do not add extra H2 sections.\n"
    )
    context = (
        f"\nReport query:\n{query}\n\n"
        f"Source documents:\n{sources}\n\n"
        f"Output plan title: {output_plan.title}\n"
        f"Selected evidence block count: {len(selected_evidence.blocks)}\n"
    )
    recursive_section = ""
    if recursive_summary.strip():
        recursive_section = (
            "\nTop ranked evidence groups for broad coverage:\n"
            f"{_truncate(recursive_summary.strip(), max(1000, max_input_chars // 2))}\n"
        )
    fixed = instructions + context + recursive_section + "\nSelected evidence for citation checks:\n"
    evidence_budget = max(800, max_input_chars - len(fixed))
    evidence_packet = format_selected_evidence(selected_evidence, max_text_chars=1200)
    return fixed + _truncate(evidence_packet, evidence_budget)


_final_markdown_prompt = final_markdown_prompt


def _emit(progress: ProgressCallback | None, kind: str, text: str) -> None:
    if progress is not None and text:
        progress(kind, text)


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Slash tool cancelled.")


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
