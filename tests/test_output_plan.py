import unittest
from pathlib import Path

from src.document_pipeline.high_level import generate_report_from_plan, write_output_plan
from src.document_pipeline.mid_level import build_doc_map, chunk_sections
from src.document_pipeline.schemas import DocumentMetadata, ExtractedBlock, ExtractedDocument, Provenance, SourceInfo


class OutputPlanTests(unittest.TestCase):
    def test_write_output_plan_assigns_chunks_and_goal(self) -> None:
        document = _sample_document()
        doc_map = build_doc_map([document])
        chunks = chunk_sections([document])

        plan = write_output_plan([document], doc_map, chunks, goal="Prepare project summary")

        self.assertEqual(plan.goal, "Prepare project summary")
        self.assertEqual(plan.source_document_ids, ["doc_report"])
        self.assertTrue(plan.sections)
        self.assertIn(chunks[0].chunk_id, plan.sections[0].source_chunk_ids)

    def test_generate_report_from_plan_uses_grounded_evidence(self) -> None:
        document = _sample_document()
        doc_map = build_doc_map([document])
        chunks = chunk_sections([document])
        plan = write_output_plan([document], doc_map, chunks)

        markdown = generate_report_from_plan(plan, [document], doc_map, chunks)

        self.assertIn("# Report for Report", markdown)
        self.assertIn("Revenue grew by 10%.", markdown)
        self.assertIn("output_plan.json", markdown)
        self.assertIn("Claims without extracted evidence", markdown)


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
