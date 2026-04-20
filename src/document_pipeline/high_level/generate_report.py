from __future__ import annotations

import json
from threading import Event
from typing import Any, Callable, Protocol

from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, LLMReportResult, OutputPlan, SelectedEvidence

from .generate_output_plan import generate_output_plan
from .select_evidence import format_selected_evidence

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
    progress: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> LLMReportResult:
    """Generate final markdown from compact selected evidence with one LLM call."""

    query = report_query.strip() or output_plan.goal
    attempts: list[dict[str, Any]] = []
    _check_cancelled(cancel_event)
    if llm_client is None:
        _emit(progress, "status", "LLM client is not configured. Using deterministic fallback report.\n")
        markdown = generate_output_plan(output_plan, documents, doc_map, selected_evidence)
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
        markdown = generate_output_plan(output_plan, documents, doc_map, selected_evidence)
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
    attempts: list[dict[str, Any]],
    progress: ProgressCallback | None,
    cancel_event: Event | None,
) -> str:
    _check_cancelled(cancel_event)
    prompt = _final_markdown_prompt(output_plan, documents, selected_evidence, query, max_input_chars)
    messages = [
        {
            "role": "system",
            "content": (
                "You write grounded Markdown reports from extracted evidence. "
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
    attempts.append(
        {
            "stage": "final_report",
            "status": "succeeded",
            "selected_evidence_block_count": len(selected_evidence.blocks),
            "llm_calls": 1,
        }
    )
    _emit(progress, "status", "\nFinal Markdown report generated.\n")
    return markdown.rstrip() + "\n"


def _final_markdown_prompt(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    selected_evidence: SelectedEvidence,
    query: str,
    max_input_chars: int,
) -> str:
    sources = [
        {
            "document_id": document.document_id,
            "filename": document.source.filename,
            "extension": document.source.extension,
            "blocks": len(document.blocks),
            "assets": len(document.assets),
        }
        for document in documents
    ]
    evidence_packet = format_selected_evidence(selected_evidence)
    payload = {
        "report_query": query,
        "output_plan": output_plan.to_dict(),
        "source_documents": sources,
        "selected_evidence_block_count": len(selected_evidence.blocks),
        "selected_evidence": evidence_packet,
    }
    return (
        "Write the final report as Markdown only.\n\n"
        "Requirements:\n"
        "- Start with one H1 title.\n"
        "- Follow the output plan sections.\n"
        "- Focus on the report query.\n"
        "- Use only the selected evidence packet.\n"
        "- Explain the reasoning that connects evidence to the answer.\n"
        "- Cite block IDs and source filenames when making concrete claims.\n"
        "- State gaps when evidence is missing.\n\n"
        f"Grounded report material:\n{_truncate(json.dumps(payload, ensure_ascii=False, indent=2), max_input_chars)}"
    )


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
