from __future__ import annotations

import re

from src.document_pipeline.schemas import ExtractedBlock, ExtractedDocument, OutputPlan, SelectedEvidence
from src.document_pipeline.schemas import SelectedEvidenceBlock


def select_evidence_blocks(
    documents: list[ExtractedDocument],
    output_plan: OutputPlan,
    query: str,
    max_input_chars: int = 12000,
) -> SelectedEvidence:
    """Select prompt-sized evidence from extracted blocks without chunking."""

    blocks = [block for document in documents for block in document.blocks if _block_text(block)]
    if not blocks:
        return SelectedEvidence(query=query, max_input_chars=max_input_chars, blocks=[])

    docs_by_id = {document.document_id: document for document in documents}
    planned_block_ids = [block_id for section in output_plan.sections for block_id in section.source_block_ids]
    terms = _query_terms(query)
    ordered = _ordered_blocks(blocks, planned_block_ids, terms)

    selected: list[SelectedEvidenceBlock] = []
    used_chars = 0
    budget = max(800, max_input_chars)
    for block in ordered:
        document = docs_by_id.get(block.document_id)
        source_filename = document.source.filename if document is not None else ""
        text = _block_text(block)
        evidence = SelectedEvidenceBlock(
            document_id=block.document_id,
            block_id=block.block_id,
            source_filename=source_filename,
            role=block.role or block.type,
            text=text,
            provenance=block.provenance,
            score=_block_score(block, terms, planned_block_ids),
        )
        formatted_len = len(_format_evidence_block(evidence))
        if selected and used_chars + formatted_len > budget:
            break
        selected.append(evidence)
        used_chars += formatted_len
    if not selected:
        block = blocks[0]
        document = docs_by_id.get(block.document_id)
        selected.append(
            SelectedEvidenceBlock(
                document_id=block.document_id,
                block_id=block.block_id,
                source_filename=document.source.filename if document is not None else "",
                role=block.role or block.type,
                text=_block_text(block),
                provenance=block.provenance,
                score=_block_score(block, terms, planned_block_ids),
            )
        )
    return SelectedEvidence(query=query, max_input_chars=max_input_chars, blocks=selected)


def format_selected_evidence(evidence: SelectedEvidence, max_text_chars: int = 1200) -> str:
    return "\n\n".join(_format_evidence_block(block, max_text_chars=max_text_chars) for block in evidence.blocks)


def _ordered_blocks(
    blocks: list[ExtractedBlock],
    planned_block_ids: list[str],
    terms: set[str],
) -> list[ExtractedBlock]:
    planned_lookup = {block_id: index for index, block_id in enumerate(planned_block_ids)}
    return sorted(
        blocks,
        key=lambda block: (
            _block_score(block, terms, planned_block_ids),
            -planned_lookup.get(block.block_id, len(planned_lookup)),
            -block.order,
        ),
        reverse=True,
    )


def _block_score(block: ExtractedBlock, terms: set[str], planned_block_ids: list[str]) -> int:
    text = _block_text(block).lower()
    score = 0
    if block.block_id in planned_block_ids:
        score += 10
    for term in terms:
        if term in text:
            score += 3
    if block.role in {"title", "heading", "section"}:
        score += 1
    return score


def _block_text(block: ExtractedBlock) -> str:
    return (block.normalized_text or block.markdown or block.text).strip()


def _format_evidence_block(block: SelectedEvidenceBlock, max_text_chars: int = 1200) -> str:
    return (
        f"source: {block.source_filename}\n"
        f"document_id: {block.document_id}\n"
        f"block_id: {block.block_id}\n"
        f"role: {block.role}\n"
        f"score: {block.score}\n"
        f"evidence:\n{_truncate(' '.join(block.text.split()), max_text_chars)}"
    )


def _query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[A-Za-z0-9가-힣_]{3,}", query.lower()))
    stopwords = {"generate", "report", "summary", "summarize", "about", "folder", "output", "this", "that"}
    return {term for term in terms if term not in stopwords}


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
