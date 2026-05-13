from __future__ import annotations

import re

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
        elif section.section_id == "key_concepts":
            lines.extend(_key_concepts_section(section.title, selected_evidence))
        elif section.section_id == "open_questions":
            lines.extend(_open_questions_section(section.title, documents, selected_evidence))
        elif section.section_id == "next_actions":
            lines.extend(_next_actions_section(section.title, documents, selected_evidence))
        elif section.section_id == "related_documents":
            lines.extend(_related_documents_section(documents, section.title))
        else:
            lines.extend(_summary_section(section.title, selected_evidence))
    return "\n".join(lines).rstrip() + "\n"


def _summary_section(title: str, selected_evidence: SelectedEvidence | None) -> list[str]:
    lines = [f"## {title}", ""]
    blocks = selected_evidence.blocks if selected_evidence is not None else []
    if not blocks:
        lines.extend(
            [
                "No selected evidence is available yet, so the report cannot summarize supported findings.",
                "",
            ]
        )
        return lines
    for block in blocks[:3]:
        source = f"{block.source_filename} / {block.block_id}".strip(" /")
        lines.append(f"- {_single_line(block.text, 260)} (`{source}`)")
    lines.append("")
    return lines


def _key_concepts_section(title: str, selected_evidence: SelectedEvidence | None) -> list[str]:
    lines = [f"## {title}", ""]
    blocks = selected_evidence.blocks if selected_evidence is not None else []
    concepts = _concept_entries(blocks)
    if not concepts:
        lines.extend(["- No concept-level evidence is available yet.", ""])
        return lines
    for concept_title, entries in concepts:
        lines.append(f"### {concept_title}")
        lines.append("")
        for entry in entries:
            lines.append(f"- {entry}")
        lines.append("")
    return lines


def _open_questions_section(
    title: str,
    documents: list[ExtractedDocument],
    selected_evidence: SelectedEvidence | None,
) -> list[str]:
    lines = [f"## {title}", ""]
    gaps: list[str] = []
    if not documents:
        gaps.append("No supported source documents were extracted from the attached folder.")
    if documents and (selected_evidence is None or not selected_evidence.blocks):
        gaps.append("Documents were extracted, but no evidence blocks were selected for report generation.")
    for document in documents:
        for warning in document.warnings:
            gaps.append(f"{document.source.filename}: {warning}")
    if not gaps:
        gaps.append("The calculation basis, assumptions, and missing cross-checks should be confirmed where the evidence stays implicit.")
        gaps.append("Topics not covered by the selected evidence remain open until more source material is reviewed.")
    lines.extend(f"- {gap}" for gap in gaps)
    lines.append("")
    return lines


def _next_actions_section(
    title: str,
    documents: list[ExtractedDocument],
    selected_evidence: SelectedEvidence | None,
) -> list[str]:
    lines = [f"## {title}", ""]
    actions = _extract_action_lines(selected_evidence.blocks if selected_evidence is not None else [])
    if not actions:
        if documents:
            actions = [
                "Validate the most important quantitative claims against the original source files.",
                "Review unresolved assumptions before using this report for downstream decisions or presentations.",
            ]
        else:
            actions = ["Attach supported documents and rerun report generation."]
    lines.extend(f"- {action}" for action in actions[:5])
    lines.append("")
    return lines


def _related_documents_section(documents: list[ExtractedDocument], title: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not documents:
        lines.extend(["- No related documents are available.", ""])
        return lines
    for document in documents:
        descriptor = (
            f"{document.source.filename} ({document.source.extension}): "
            f"{len(document.blocks)} block(s), {len(document.assets)} asset(s)."
        )
        lines.append(f"- {descriptor}")
    lines.append("")
    return lines


def _concept_entries(blocks) -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []
    seen_titles: set[str] = set()
    for block in blocks:
        title = _concept_title(block.text)
        source = f"{block.source_filename} / {block.block_id}".strip(" /")
        entry = f"{_single_line(block.text, 260)} (`{source}`)"
        if title in seen_titles:
            for existing_title, existing_entries in entries:
                if existing_title == title:
                    if entry not in existing_entries:
                        existing_entries.append(entry)
                    break
            continue
        seen_titles.add(title)
        entries.append((title, [entry]))
    return entries[:8]


def _concept_title(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return "Concept"
    if ":" in cleaned:
        return cleaned.split(":", 1)[0][:80].strip() or "Concept"
    words = re.findall(r"[A-Za-z0-9가-힣_./-]+", cleaned)
    if not words:
        return "Concept"
    return " ".join(words[:6])[:80]


def _extract_action_lines(blocks) -> list[str]:
    actions: list[str] = []
    for block in blocks:
        text = " ".join(block.text.split())
        lowered = text.lower()
        if any(term in lowered for term in ("next step", "follow-up", "action", "todo", "verify", "check", "review", "validate")):
            actions.append(_single_line(text, 220))
    return actions


def _single_line(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
