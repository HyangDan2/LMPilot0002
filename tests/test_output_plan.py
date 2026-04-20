import unittest
from pathlib import Path

from src.document_pipeline.high_level import generate_output_plan, write_output_plan
from src.document_pipeline.high_level.select_evidence import select_evidence_blocks
from src.document_pipeline.mid_level import build_doc_map
from src.document_pipeline.schemas import DocumentMetadata, ExtractedBlock, ExtractedDocument, Provenance, SourceInfo


class OutputPlanTests(unittest.TestCase):
    def test_write_output_plan_uses_three_engineering_sections(self) -> None:
        document = _sample_document()
        doc_map = build_doc_map([document])

        plan = write_output_plan([document], doc_map, goal="Prepare project summary")

        self.assertEqual(plan.goal, "Prepare project summary")
        self.assertEqual(plan.source_document_ids, ["doc_report"])
        self.assertEqual(
            [section.title for section in plan.sections],
            ["Summary", "Source Documents", "Open Issues and Next Actions"],
        )
        self.assertEqual(plan.sections[0].max_chars, 20480)
        self.assertIn("blk_001", plan.sections[0].source_block_ids)

    def test_generate_output_plan_uses_grounded_evidence(self) -> None:
        document = _sample_document()
        doc_map = build_doc_map([document])
        plan = write_output_plan([document], doc_map)
        selected_evidence = select_evidence_blocks([document], plan, plan.goal)

        markdown = generate_output_plan(plan, [document], doc_map, selected_evidence)

        self.assertIn("# Engineering Report for Report", markdown)
        self.assertIn("## Summary", markdown)
        self.assertIn("### Objective", markdown)
        self.assertIn("### Engineering Context", markdown)
        self.assertIn("### Key Findings", markdown)
        self.assertIn("### Quantitative Results", markdown)
        self.assertIn("## Source Documents", markdown)
        self.assertIn("## Open Issues and Next Actions", markdown)
        self.assertIn("Revenue grew by 10%.", markdown)
        self.assertNotIn("## Provenance", markdown)


def _sample_document() -> ExtractedDocument:
    source_path = str(Path("work") / "report.pptx")
    provenance = Provenance(source_path=source_path, location_type="slide", slide=1)
    return ExtractedDocument(
        schema_version="0.1",
        document_id="doc_report",
        source=SourceInfo(
            path=source_path,
            filename="report.pptx",
            extension=".pptx",
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            size_bytes=6,
            sha256="abc",
        ),
        metadata=DocumentMetadata(title="Report"),
        blocks=[
            ExtractedBlock(
                block_id="blk_001",
                document_id="doc_report",
                type="text",
                role="section",
                order=0,
                text="Revenue grew by 10%.",
                normalized_text="Revenue grew by 10%.",
                provenance=provenance,
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
