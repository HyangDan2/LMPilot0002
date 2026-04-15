import tempfile
import unittest
from pathlib import Path

from app.ingestion.scanner import scan_supported_files
from app.planner.planner import PlannerError, parse_presentation_plan
from src.tools.render_pptx import parse_render_pptx_arguments


class RenderPptxPipelineTests(unittest.TestCase):
    def test_scanner_finds_supported_files_recursively(self) -> None:
        root = Path(tempfile.mkdtemp())
        nested = root / "nested"
        nested.mkdir()
        docx = root / "brief.docx"
        pdf = nested / "report.pdf"
        ignored = root / "notes.txt"
        docx.write_bytes(b"placeholder")
        pdf.write_bytes(b"placeholder")
        ignored.write_text("skip", encoding="utf-8")

        self.assertEqual(scan_supported_files(root), [docx.resolve(), pdf.resolve()])

    def test_parse_presentation_plan_accepts_strict_json(self) -> None:
        plan = parse_presentation_plan(
            """
            {
              "output_type": "pptx",
              "title": "Executive Summary",
              "target_audience": "Leadership",
              "slides": [
                {
                  "slide_title": "Overview",
                  "purpose": "Summarize the opportunity",
                  "source_refs": ["doc-1-section-1"],
                  "image_refs": []
                }
              ]
            }
            """
        )

        self.assertEqual(plan.title, "Executive Summary")
        self.assertEqual(plan.slides[0].source_refs, ["doc-1-section-1"])

    def test_parse_presentation_plan_rejects_invalid_json(self) -> None:
        with self.assertRaises(PlannerError):
            parse_presentation_plan("not json")

    def test_render_pptx_command_arguments_support_flags_and_goal(self) -> None:
        options = parse_render_pptx_arguments(
            "--working-dir docs --output-dir out --base-url http://localhost:8000/v1 "
            "--model local Create a 5-slide briefing"
        )

        self.assertEqual(options.working_dir, "docs")
        self.assertEqual(options.output_dir, "out")
        self.assertEqual(options.base_url, "http://localhost:8000/v1")
        self.assertEqual(options.model, "local")
        self.assertEqual(options.goal, "Create a 5-slide briefing")


if __name__ == "__main__":
    unittest.main()

