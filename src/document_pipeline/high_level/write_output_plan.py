from __future__ import annotations

from src.document_pipeline.schemas import DocumentMap, ExtractedDocument, OutputPlan, OutputPlanSection


DEFAULT_REPORT_GOAL = "Generate a concise engineering report from the attached workspace documents."
OUTPUT_PLAN_SCHEMA_VERSION = "0.1"
SUMMARY_SUBSECTIONS = [
    "What the Document Explicitly Describes",
    "Main Methods or Components Explicitly Mentioned",
    "Quantitative Values Explicitly Present",
    "Explicit Limitations or Constraints",
    "Unclear or Not Specified in Selected Evidence",
]
<<<<<<< HEAD
=======
REPORT_SECTION_TITLES = [
    "Summary",
    "Key Concepts",
    "Open Questions",
    "Next Actions",
    "Related Documents",
]
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3


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
            section_id="summary",
            title="Summary",
            purpose=(
<<<<<<< HEAD
                "Provide an evidence-grounded summary that separates explicit document content, "
                "explicitly mentioned methods or components, quantitative values, explicit "
                "limitations or constraints, and facts not specified in the selected evidence."
            ),
            source_block_ids=all_block_ids[:12],
            max_chars=20480,
        ),
        OutputPlanSection(
            section_id="source_documents",
            title="Source Documents",
            purpose="List source files used for traceability without exposing pipeline internals.",
            source_block_ids=all_block_ids[:10],
            max_chars=200,
        ),
        OutputPlanSection(
            section_id="open_issues",
            title="Open Issues and Next Actions",
            purpose="Name missing evidence, unclear assumptions, parser limitations, and concrete follow-up actions.",
            source_block_ids=[],
            max_chars=200,
=======
                "Provide a compact executive summary of the document set. "
                "This section should be brief relative to the rest of the report."
            ),
            source_block_ids=all_block_ids[:12],
            max_chars=1200,
        ),
        OutputPlanSection(
            section_id="key_concepts",
            title="Key Concepts",
            purpose=(
                "Explain the important concepts in engineering terms and cover the full set of concepts "
                "present across the source documents."
            ),
            source_block_ids=all_block_ids,
            max_chars=6000,
        ),
        OutputPlanSection(
            section_id="open_questions",
            title="Open Questions",
            purpose="Identify unresolved questions, missing evidence, and ambiguities that remain after reading the sources.",
            source_block_ids=all_block_ids[:8],
            max_chars=1200,
        ),
        OutputPlanSection(
            section_id="next_actions",
            title="Next Actions",
            purpose="List practical engineering follow-up actions, checks, or validation tasks suggested by the evidence.",
            source_block_ids=all_block_ids[:8],
            max_chars=1200,
        ),
        OutputPlanSection(
            section_id="related_documents",
            title="Related Documents",
            purpose="List related source files and their relevance to the report topic.",
            source_block_ids=all_block_ids[:10],
            max_chars=800,
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
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
        return f"Engineering Report for {title}"
    if documents:
        return f"Engineering Report for {len(documents)} Documents"
    return "Engineering Report"
