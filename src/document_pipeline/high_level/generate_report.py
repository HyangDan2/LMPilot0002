from __future__ import annotations

from pathlib import Path

from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument, OutputPlan


def generate_report_from_plan(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    doc_map: DocumentMap | None = None,
    chunks: list[EvidenceChunk] | None = None,
) -> str:
    """Write a grounded markdown report from a precomputed output plan."""

    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks or []}
    lines = [
        f"# {output_plan.title}",
        "",
        f"Goal: {output_plan.goal}",
        "",
        "This report is generated from extracted evidence only. Claims without extracted evidence are left as gaps.",
        "",
    ]
    for section in output_plan.sections:
        if section.section_id == "overview":
            lines.extend(_overview_section(documents, section.title))
        elif section.section_id == "source_documents":
            lines.extend(_source_documents_section(documents, section.title))
        elif section.section_id == "key_evidence":
            lines.extend(_key_evidence_section(section.title, section.source_chunk_ids, chunks_by_id))
        elif section.section_id == "provenance":
            lines.extend(_provenance_section(section.title, documents, doc_map, chunks or []))
        elif section.section_id == "gaps":
            lines.extend(_gaps_section(section.title, documents, chunks or []))
        else:
            lines.extend(_generic_section(section.title, section.source_chunk_ids, chunks_by_id))
    return "\n".join(lines).rstrip() + "\n"


def _overview_section(documents: list[ExtractedDocument], title: str) -> list[str]:
    block_count = sum(len(document.blocks) for document in documents)
    asset_count = sum(len(document.assets) for document in documents)
    return [
        f"## {title}",
        "",
        f"- Documents processed: {len(documents)}",
        f"- Extracted blocks: {block_count}",
        f"- Extracted assets: {asset_count}",
        "",
    ]


def _source_documents_section(documents: list[ExtractedDocument], title: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Document | Type | Blocks | Assets |",
        "|---|---:|---:|---:|",
    ]
    if not documents:
        lines.append("| none |  | 0 | 0 |")
    for document in documents:
        lines.append(
            "| "
            f"{_escape_table(document.source.filename)} | "
            f"{_escape_table(document.source.extension)} | "
            f"{len(document.blocks)} | "
            f"{len(document.assets)} |"
        )
    lines.append("")
    return lines


def _key_evidence_section(title: str, chunk_ids: list[str], chunks_by_id: dict[str, EvidenceChunk]) -> list[str]:
    lines = [f"## {title}", ""]
    if not chunk_ids:
        lines.extend(["_No evidence chunks are available yet._", ""])
        return lines
    for index, chunk_id in enumerate(chunk_ids, start=1):
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        lines.extend(
            [
                f"### Evidence {index}",
                "",
                f"- chunk_id: `{chunk.chunk_id}`",
                f"- document_id: `{chunk.document_id}`",
                f"- source_blocks: {', '.join(f'`{block_id}`' for block_id in chunk.block_ids)}",
                "",
                _quote_block(_single_line(chunk.text, 700)),
                "",
            ]
        )
    if len(lines) == 2:
        lines.extend(["_Planned evidence chunks were not found in the current chunk set._", ""])
    return lines


def _provenance_section(
    title: str,
    documents: list[ExtractedDocument],
    doc_map: DocumentMap | None,
    chunks: list[EvidenceChunk],
) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "Saved pipeline artifacts:",
        "",
        "- `llm_result/document_pipeline/extracted_documents.json`",
        "- `llm_result/document_pipeline/extraction_manifest.json`",
        "- `llm_result/document_pipeline/document_map.json`",
        "- `llm_result/document_pipeline/chunks.json`",
        "- `llm_result/document_pipeline/output_plan.json`",
        "- `llm_result/document_pipeline/generated_report.md`",
        "",
        "Source paths:",
    ]
    if documents:
        lines.extend(f"- `{_display_path(document.source.path)}`" for document in documents)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"Document-map blocks: {len(doc_map.blocks) if doc_map is not None else 0}",
            f"Evidence chunks: {len(chunks)}",
            "",
        ]
    )
    return lines


def _gaps_section(title: str, documents: list[ExtractedDocument], chunks: list[EvidenceChunk]) -> list[str]:
    lines = [f"## {title}", ""]
    gaps = []
    if not documents:
        gaps.append("No supported source documents were extracted from the attached folder.")
    if documents and not chunks:
        gaps.append("Documents were extracted, but no retrieval chunks were produced.")
    for document in documents:
        if document.warnings:
            gaps.extend(f"{document.source.filename}: {warning}" for warning in document.warnings)
    if not gaps:
        gaps.append("No extraction warnings were recorded. Review generated evidence before using the report externally.")
    lines.extend(f"- {gap}" for gap in gaps)
    lines.append("")
    return lines


def _generic_section(title: str, chunk_ids: list[str], chunks_by_id: dict[str, EvidenceChunk]) -> list[str]:
    lines = [f"## {title}", ""]
    for chunk_id in chunk_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is not None:
            lines.extend([_quote_block(_single_line(chunk.text, 500)), ""])
    if len(lines) == 2:
        lines.extend(["_No evidence assigned._", ""])
    return lines


def _single_line(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _quote_block(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def _escape_table(text: str) -> str:
    return text.replace("|", "\\|")


def _display_path(path: str) -> str:
    return Path(path).name if path else ""
