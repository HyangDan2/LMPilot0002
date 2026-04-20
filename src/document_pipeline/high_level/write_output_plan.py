from __future__ import annotations

from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, OutputPlanSection


DEFAULT_REPORT_GOAL = "Generate a grounded markdown report from the attached workspace documents."
OUTPUT_PLAN_SCHEMA_VERSION = "0.1"


def write_output_plan(
    documents: list[ExtractedDocument],
    doc_map: DocumentMap | None = None,
    goal: str = DEFAULT_REPORT_GOAL,
) -> OutputPlan:
    """Create a deterministic report plan from extracted evidence."""

    all_block_ids = [block.block_id for document in documents for block in document.blocks]
    title = _plan_title(documents)
    sections = [
        OutputPlanSection(
            section_id="overview",
            title="Overview",
            purpose="State the report goal and summarize available source coverage.",
            source_block_ids=all_block_ids[:5],
            max_chars=1000,
        ),
        OutputPlanSection(
            section_id="source_documents",
            title="Source Documents",
            purpose="List source files, document types, block counts, and reusable assets.",
            source_block_ids=all_block_ids[:10],
            max_chars=1200,
        ),
        OutputPlanSection(
            section_id="key_evidence",
            title="Key Evidence",
            purpose="Surface the strongest extracted evidence blocks without inventing facts.",
            source_block_ids=all_block_ids[:12],
            max_chars=2200,
        ),
        OutputPlanSection(
            section_id="provenance",
            title="Provenance",
            purpose="Explain where the report evidence came from and which artifacts were created.",
            source_block_ids=all_block_ids,
            max_chars=1400,
        ),
        OutputPlanSection(
            section_id="gaps",
            title="Gaps and Next Checks",
            purpose="Name missing evidence, parser limitations, and useful follow-up checks.",
            max_chars=1000,
        ),
    ]
    return OutputPlan(
        schema_version=OUTPUT_PLAN_SCHEMA_VERSION,
        title=title,
        goal=goal.strip() or DEFAULT_REPORT_GOAL,
        sections=sections,
        source_document_ids=[document.document_id for document in documents],
    )


def _plan_title(documents: list[ExtractedDocument]) -> str:
    if len(documents) == 1:
        title = documents[0].metadata.title or documents[0].source.filename
        return f"Report for {title}"
    if documents:
        return f"Workspace Report for {len(documents)} Documents"
    return "Workspace Report"
