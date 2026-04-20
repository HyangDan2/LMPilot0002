from __future__ import annotations

import json
import re
from threading import Event
from typing import Any, Callable, Protocol

from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument, LLMReportResult, OutputPlan

from .generate_output_plan import generate_output_plan

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
    chunks: list[EvidenceChunk],
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
        markdown = generate_output_plan(output_plan, documents, doc_map, chunks)
        _emit(progress, "markdown", markdown)
        return LLMReportResult(
            markdown=markdown,
            attempts=[{"stage": "final_report", "status": "fallback", "error": "LLM client is not configured."}],
            used_llm=False,
            fallback_reason="LLM client is not configured.",
        )

    selected_chunks = select_evidence_chunks(output_plan, chunks, query, max_input_chars)
    _check_cancelled(cancel_event)
    _emit(progress, "status", f"Selected {len(selected_chunks)} evidence chunk(s) for the final LLM prompt.\n")
    try:
        markdown = _write_final_markdown(
            llm_client=llm_client,
            output_plan=output_plan,
            documents=documents,
            selected_chunks=selected_chunks,
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
        markdown = generate_output_plan(output_plan, documents, doc_map, chunks)
        _emit(progress, "status", f"Final LLM report failed. Using deterministic fallback: {exc}\n")
        _emit(progress, "markdown", markdown)
        attempts.append({"stage": "final_report", "status": "fallback", "error": str(exc)})
        return LLMReportResult(
            markdown=markdown,
            attempts=attempts,
            used_llm=False,
            fallback_reason=str(exc),
        )


def select_evidence_chunks(
    output_plan: OutputPlan,
    chunks: list[EvidenceChunk],
    query: str,
    max_input_chars: int,
) -> list[EvidenceChunk]:
    """Select compact evidence for the final prompt without LLM summarization."""

    if not chunks:
        return []
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    planned_ids = [chunk_id for section in output_plan.sections for chunk_id in section.source_chunk_ids]
    query_terms = _query_terms(query)
    scored = sorted(
        chunks,
        key=lambda chunk: (
            _chunk_score(chunk, query_terms, planned_ids),
            -chunks.index(chunk),
        ),
        reverse=True,
    )
    ordered: list[EvidenceChunk] = []
    seen: set[str] = set()
    for chunk_id in planned_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is not None and chunk.chunk_id not in seen:
            ordered.append(chunk)
            seen.add(chunk.chunk_id)
    for chunk in scored:
        if chunk.chunk_id not in seen:
            ordered.append(chunk)
            seen.add(chunk.chunk_id)

    selected: list[EvidenceChunk] = []
    used_chars = 0
    budget = max(800, max_input_chars)
    for chunk in ordered:
        formatted_len = len(_format_chunk(chunk, max_text_chars=900))
        if selected and used_chars + formatted_len > budget:
            break
        selected.append(chunk)
        used_chars += formatted_len
    return selected or chunks[:1]


def _write_final_markdown(
    *,
    llm_client: ReportLLMClient,
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    selected_chunks: list[EvidenceChunk],
    query: str,
    max_input_chars: int,
    attempts: list[dict[str, Any]],
    progress: ProgressCallback | None,
    cancel_event: Event | None,
) -> str:
    _check_cancelled(cancel_event)
    prompt = _final_markdown_prompt(output_plan, documents, selected_chunks, query, max_input_chars)
    messages = [
        {
            "role": "system",
            "content": (
                "You write grounded Markdown reports from extracted evidence. "
                "Return Markdown only. Do not invent unsupported facts. Cite chunk IDs for concrete claims."
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
            "selected_chunk_count": len(selected_chunks),
            "llm_calls": 1,
        }
    )
    _emit(progress, "status", "\nFinal Markdown report generated.\n")
    return markdown.rstrip() + "\n"


def _final_markdown_prompt(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    selected_chunks: list[EvidenceChunk],
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
    evidence_packet = "\n\n".join(_format_chunk(chunk) for chunk in selected_chunks)
    payload = {
        "report_query": query,
        "output_plan": output_plan.to_dict(),
        "source_documents": sources,
        "selected_evidence_chunk_count": len(selected_chunks),
        "selected_evidence": evidence_packet,
    }
    return (
        "Write the final report as Markdown only.\n\n"
        "Requirements:\n"
        "- Start with one H1 title.\n"
        "- Follow the output plan sections.\n"
        "- Focus on the report query.\n"
        "- Use only the selected evidence packet.\n"
        "- Cite chunk IDs such as `chunk_abc` when making concrete claims.\n"
        "- State gaps when evidence is missing.\n\n"
        f"Grounded report material:\n{_truncate(json.dumps(payload, ensure_ascii=False, indent=2), max_input_chars)}"
    )


def _format_chunk(chunk: EvidenceChunk, max_text_chars: int = 1200) -> str:
    return (
        f"chunk_id: {chunk.chunk_id}\n"
        f"document_id: {chunk.document_id}\n"
        f"block_ids: {', '.join(chunk.block_ids)}\n"
        f"evidence:\n{_truncate(' '.join(chunk.text.split()), max_text_chars)}"
    )


def _chunk_score(chunk: EvidenceChunk, query_terms: set[str], planned_ids: list[str]) -> int:
    text = chunk.text.lower()
    score = 0
    if chunk.chunk_id in planned_ids:
        score += 10
    for term in query_terms:
        if term in text:
            score += 3
    return score


def _query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[A-Za-z0-9가-힣_]{3,}", query.lower()))
    stopwords = {"generate", "report", "summary", "summarize", "about", "folder", "output", "this", "that"}
    return {term for term in terms if term not in stopwords}


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
