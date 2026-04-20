from __future__ import annotations

from pathlib import Path

from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, SelectedEvidence


def generate_output_plan(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    doc_map: DocumentMap | None = None,
    selected_evidence: SelectedEvidence | None = None,
) -> str:
    """Write a deterministic markdown fallback from output plan and selected blocks."""

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
            lines.extend(_selected_evidence_section(section.title, selected_evidence))
        elif section.section_id == "provenance":
            lines.extend(_provenance_section(section.title, documents, doc_map, selected_evidence))
        elif section.section_id == "gaps":
            lines.extend(_gaps_section(section.title, documents, selected_evidence))
        else:
            lines.extend(_selected_evidence_section(section.title, selected_evidence))
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


def _selected_evidence_section(title: str, selected_evidence: SelectedEvidence | None) -> list[str]:
    lines = [f"## {title}", ""]
    blocks = selected_evidence.blocks if selected_evidence is not None else []
    if not blocks:
        lines.extend(["_No selected evidence blocks are available._", ""])
        return lines
    for index, block in enumerate(blocks[:12], start=1):
        lines.extend(
            [
                f"### Evidence {index}",
                "",
                f"- source: `{block.source_filename}`",
                f"- block_id: `{block.block_id}`",
                f"- role: {block.role}",
                "",
                _quote_block(_single_line(block.text, 700)),
                "",
            ]
        )
    if len(blocks) > 12:
        lines.append(f"_ {len(blocks) - 12} more selected evidence block(s) omitted._")
    return lines


def _provenance_section(
    title: str,
    documents: list[ExtractedDocument],
    doc_map: DocumentMap | None,
    selected_evidence: SelectedEvidence | None,
) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "Saved pipeline artifacts:",
        "",
        "- `llm_result/document_pipeline/extracted_documents.json`",
        "- `llm_result/document_pipeline/extraction_manifest.json`",
        "- `llm_result/document_pipeline/document_map.json`",
        "- `llm_result/document_pipeline/output_plan.json`",
        "- `llm_result/document_pipeline/selected_evidence.json`",
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
            f"Selected evidence blocks: {len(selected_evidence.blocks) if selected_evidence is not None else 0}",
            "",
        ]
    )
    return lines


def _gaps_section(
    title: str,
    documents: list[ExtractedDocument],
    selected_evidence: SelectedEvidence | None,
) -> list[str]:
    lines = [f"## {title}", ""]
    gaps = []
    if not documents:
        gaps.append("No supported source documents were extracted from the attached folder.")
    if documents and (selected_evidence is None or not selected_evidence.blocks):
        gaps.append("Documents were extracted, but no evidence blocks were selected.")
    for document in documents:
        if document.warnings:
            gaps.extend(f"{document.source.filename}: {warning}" for warning in document.warnings)
    if not gaps:
        gaps.append("No extraction warnings were recorded. Review selected evidence before using the report externally.")
    lines.extend(f"- {gap}" for gap in gaps)
    lines.append("")
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
