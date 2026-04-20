from __future__ import annotations

import json
from typing import Any, Protocol

from src.document_pipeline.schemas import (
    ChunkSummary,
    DocumentMap,
    EvidenceChunk,
    ExtractedDocument,
    LLMReportResult,
    OutputPlan,
    SectionSummary,
)

from .generate_output_plan import generate_output_plan


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
) -> LLMReportResult:
    """Generate final markdown with context-safe LLM orchestration."""

    query = report_query.strip() or output_plan.goal
    attempts: list[dict[str, Any]] = []
    if llm_client is None:
        markdown = generate_output_plan(output_plan, documents, doc_map, chunks)
        return LLMReportResult(
            markdown=markdown,
            attempts=[{"stage": "final", "status": "fallback", "error": "LLM client is not configured."}],
            used_llm=False,
            fallback_reason="LLM client is not configured.",
        )

    try:
        chunk_summaries = _summarize_chunks(
            llm_client=llm_client,
            output_plan=output_plan,
            chunks=chunks,
            query=query,
            max_input_chars=max_input_chars,
            attempts=attempts,
        )
        section_summaries = _summarize_sections(
            llm_client=llm_client,
            output_plan=output_plan,
            chunk_summaries=chunk_summaries,
            query=query,
            max_input_chars=max_input_chars,
            attempts=attempts,
        )
        markdown = _write_final_markdown(
            llm_client=llm_client,
            output_plan=output_plan,
            documents=documents,
            section_summaries=section_summaries,
            query=query,
            max_input_chars=max_input_chars,
            attempts=attempts,
        )
        return LLMReportResult(
            markdown=markdown,
            chunk_summaries=chunk_summaries,
            section_summaries=section_summaries,
            attempts=attempts,
            used_llm=True,
        )
    except Exception as exc:
        markdown = generate_output_plan(output_plan, documents, doc_map, chunks)
        attempts.append({"stage": "pipeline", "status": "fallback", "error": str(exc)})
        return LLMReportResult(
            markdown=markdown,
            attempts=attempts,
            used_llm=False,
            fallback_reason=str(exc),
        )


def _summarize_chunks(
    *,
    llm_client: ReportLLMClient,
    output_plan: OutputPlan,
    chunks: list[EvidenceChunk],
    query: str,
    max_input_chars: int,
    attempts: list[dict[str, Any]],
) -> list[ChunkSummary]:
    summaries: list[ChunkSummary] = []
    for batch_index, batch in enumerate(_batch_chunks(chunks, max_input_chars), start=1):
        summary_id = f"chunk_summary_{batch_index:03d}"
        prompt = _chunk_summary_prompt(output_plan, batch, query)
        try:
            content = llm_client.chat_completion(
                [
                    {"role": "system", "content": _json_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            payload = _parse_json_object(content)
            summary = ChunkSummary(
                summary_id=summary_id,
                chunk_ids=[chunk.chunk_id for chunk in batch],
                summary=_string(payload.get("summary")),
                key_points=_string_list(payload.get("key_points")),
                source_refs=_string_list(payload.get("source_refs")),
            )
            if not summary.summary:
                raise ValueError("Chunk summary response did not include summary.")
            attempts.append({"stage": "chunk_summary", "batch": batch_index, "status": "succeeded"})
        except Exception as exc:
            attempts.append({"stage": "chunk_summary", "batch": batch_index, "status": "fallback", "error": str(exc)})
            summary = _fallback_chunk_summary(summary_id, batch, str(exc))
        summaries.append(summary)
    return summaries


def _summarize_sections(
    *,
    llm_client: ReportLLMClient,
    output_plan: OutputPlan,
    chunk_summaries: list[ChunkSummary],
    query: str,
    max_input_chars: int,
    attempts: list[dict[str, Any]],
) -> list[SectionSummary]:
    summaries_by_chunk = {chunk_id: summary for summary in chunk_summaries for chunk_id in summary.chunk_ids}
    section_summaries: list[SectionSummary] = []
    for section in output_plan.sections:
        selected = [summaries_by_chunk[chunk_id] for chunk_id in section.source_chunk_ids if chunk_id in summaries_by_chunk]
        if not selected and section.section_id in {"overview", "gaps", "source_documents", "provenance"}:
            selected = chunk_summaries[: min(3, len(chunk_summaries))]
        prompt = _section_summary_prompt(section.title, section.purpose, selected, query, max_input_chars)
        try:
            content = llm_client.chat_completion(
                [
                    {"role": "system", "content": _json_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            payload = _parse_json_object(content)
            summary = SectionSummary(
                section_id=section.section_id,
                title=section.title,
                summary=_string(payload.get("summary")),
                key_points=_string_list(payload.get("key_points")),
                source_refs=_string_list(payload.get("source_refs")),
                chunk_summary_ids=[item.summary_id for item in selected],
            )
            if not summary.summary:
                raise ValueError("Section summary response did not include summary.")
            attempts.append({"stage": "section_summary", "section": section.section_id, "status": "succeeded"})
        except Exception as exc:
            attempts.append(
                {"stage": "section_summary", "section": section.section_id, "status": "fallback", "error": str(exc)}
            )
            summary = _fallback_section_summary(section.section_id, section.title, selected)
        section_summaries.append(summary)
    return section_summaries


def _write_final_markdown(
    *,
    llm_client: ReportLLMClient,
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    section_summaries: list[SectionSummary],
    query: str,
    max_input_chars: int,
    attempts: list[dict[str, Any]],
) -> str:
    prompt = _final_markdown_prompt(output_plan, documents, section_summaries, query, max_input_chars)
    content = llm_client.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You write grounded Markdown reports from extracted evidence. "
                    "Return Markdown only. Do not invent unsupported facts. Keep source refs when useful."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    )
    markdown = content.strip()
    if not markdown:
        raise ValueError("Final report response was empty.")
    if not markdown.startswith("#"):
        markdown = f"# {output_plan.title}\n\n{markdown}"
    attempts.append({"stage": "final_report", "status": "succeeded"})
    return markdown.rstrip() + "\n"


def _batch_chunks(chunks: list[EvidenceChunk], max_input_chars: int) -> list[list[EvidenceChunk]]:
    if not chunks:
        return []
    budget = max(800, max_input_chars)
    batches: list[list[EvidenceChunk]] = []
    current: list[EvidenceChunk] = []
    current_len = 0
    for chunk in chunks:
        chunk_len = len(_format_chunk(chunk))
        if current and current_len + chunk_len > budget:
            batches.append(current)
            current = []
            current_len = 0
        current.append(chunk)
        current_len += chunk_len
    if current:
        batches.append(current)
    return batches


def _chunk_summary_prompt(output_plan: OutputPlan, batch: list[EvidenceChunk], query: str) -> str:
    chunks_text = "\n\n".join(_format_chunk(chunk) for chunk in batch)
    return (
        "Summarize this evidence batch for the report query.\n\n"
        f"Report query:\n{query}\n\n"
        f"Output plan title:\n{output_plan.title}\n\n"
        "Rules:\n"
        "- Use only the evidence below.\n"
        "- Preserve chunk IDs in source_refs.\n"
        "- Return JSON with summary, key_points, source_refs.\n\n"
        f"Evidence:\n{chunks_text}"
    )


def _section_summary_prompt(
    title: str,
    purpose: str,
    selected: list[ChunkSummary],
    query: str,
    max_input_chars: int,
) -> str:
    summary_text = _truncate(
        json.dumps([summary.to_dict() for summary in selected], ensure_ascii=False, indent=2),
        max_input_chars,
    )
    return (
        "Create a section-level summary from chunk summaries.\n\n"
        f"Report query:\n{query}\n\n"
        f"Section title: {title}\n"
        f"Section purpose: {purpose}\n\n"
        "Rules:\n"
        "- Use only the chunk summaries below.\n"
        "- Preserve source_refs.\n"
        "- Return JSON with summary, key_points, source_refs.\n\n"
        f"Chunk summaries:\n{summary_text}"
    )


def _final_markdown_prompt(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    section_summaries: list[SectionSummary],
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
    payload = {
        "report_query": query,
        "output_plan": output_plan.to_dict(),
        "source_documents": sources,
        "section_summaries": [summary.to_dict() for summary in section_summaries],
    }
    return (
        "Write the final report as Markdown only.\n\n"
        "Requirements:\n"
        "- Start with one H1 title.\n"
        "- Follow the output plan sections.\n"
        "- Focus on the report query.\n"
        "- Use source refs such as chunk IDs when making concrete claims.\n"
        "- State gaps when evidence is missing.\n\n"
        f"Grounded report material:\n{_truncate(json.dumps(payload, ensure_ascii=False, indent=2), max_input_chars)}"
    )


def _format_chunk(chunk: EvidenceChunk) -> str:
    return (
        f"chunk_id: {chunk.chunk_id}\n"
        f"document_id: {chunk.document_id}\n"
        f"block_ids: {', '.join(chunk.block_ids)}\n"
        f"text:\n{chunk.text}"
    )


def _fallback_chunk_summary(summary_id: str, batch: list[EvidenceChunk], error: str) -> ChunkSummary:
    text = " ".join(chunk.text for chunk in batch)
    chunk_ids = [chunk.chunk_id for chunk in batch]
    return ChunkSummary(
        summary_id=summary_id,
        chunk_ids=chunk_ids,
        summary=_truncate(" ".join(text.split()), 900) or "No chunk text was available.",
        key_points=[_truncate(" ".join(chunk.text.split()), 240) for chunk in batch[:5] if chunk.text.strip()],
        source_refs=chunk_ids,
        fallback=True,
        errors=[error],
    )


def _fallback_section_summary(section_id: str, title: str, selected: list[ChunkSummary]) -> SectionSummary:
    text = " ".join(summary.summary for summary in selected)
    refs: list[str] = []
    for summary in selected:
        refs.extend(summary.source_refs)
    return SectionSummary(
        section_id=section_id,
        title=title,
        summary=_truncate(" ".join(text.split()), 900) or "No evidence was assigned to this section.",
        key_points=[point for summary in selected for point in summary.key_points[:2]][:8],
        source_refs=_dedupe(refs),
        chunk_summary_ids=[summary.summary_id for summary in selected],
        fallback=True,
    )


def _json_system_prompt() -> str:
    return "You summarize extracted evidence. Return valid JSON only. Do not invent unsupported facts."


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    return payload


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
