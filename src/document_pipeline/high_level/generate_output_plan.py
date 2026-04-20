from __future__ import annotations

from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, SelectedEvidence


def generate_output_plan(
    output_plan: OutputPlan,
    documents: list[ExtractedDocument],
    doc_map: DocumentMap | None = None,
    selected_evidence: SelectedEvidence | None = None,
) -> str:
    """Write a deterministic markdown fallback from output plan and selected blocks."""

    lines = [f"# {output_plan.title}", ""]
    for section in output_plan.sections:
        if section.section_id == "summary":
            lines.extend(_summary_section(section.title, selected_evidence))
        elif section.section_id == "source_documents":
            lines.extend(_source_documents_section(documents, section.title))
        elif section.section_id == "open_issues":
            lines.extend(_open_issues_section(section.title, documents, selected_evidence))
        else:
            lines.extend(_summary_section(section.title, selected_evidence))
    return "\n".join(lines).rstrip() + "\n"


def _summary_section(title: str, selected_evidence: SelectedEvidence | None) -> list[str]:
    lines = [f"## {title}", ""]
    blocks = selected_evidence.blocks if selected_evidence is not None else []
    if not blocks:
        lines.extend(
            [
                "- No selected evidence blocks are available, so no engineering findings can be stated yet.",
                "- Attach supported source documents or refresh extraction before using this report externally.",
                "",
            ]
        )
        return lines
    for block in blocks[:8]:
        source = f"{block.source_filename} / {block.block_id}".strip(" /")
        lines.append(f"- {_single_line(block.text, 320)} (`{source}`)")
    if len(blocks) > 8:
        lines.append(f"- {len(blocks) - 8} additional evidence block(s) were omitted from this fallback summary.")
    lines.append("")
    return lines


def _source_documents_section(documents: list[ExtractedDocument], title: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Source | Type | Blocks | Assets |",
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


def _open_issues_section(
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
        gaps.append("Review cited evidence before using this engineering report externally.")
        gaps.append("Verify any assumptions, calculations, and recommendations against source documents.")
    lines.extend(f"- {gap}" for gap in gaps)
    lines.append("")
    return lines


def _single_line(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _escape_table(text: str) -> str:
    return text.replace("|", "\\|")
