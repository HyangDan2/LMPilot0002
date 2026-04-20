import json
import tempfile
import unittest
from pathlib import Path

from src.document_pipeline.high_level import generate_report_pipeline


class GenerateReportPipelineTests(unittest.TestCase):
    def test_generate_report_pipeline_saves_plan_and_report_for_empty_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events: list[tuple[str, str]] = []

            result = generate_report_pipeline(root, goal="Demo report", progress=lambda kind, text: events.append((kind, text)))

            output_dir = root / "llm_result" / "document_pipeline"
            plan_path = output_dir / "output_plan.json"
            report_path = output_dir / "generated_report.md"
            selected_evidence_path = output_dir / "selected_evidence.json"
            self.assertTrue(plan_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(selected_evidence_path.exists())
            self.assertEqual(json.loads(plan_path.read_text(encoding="utf-8"))["goal"], "Demo report")
            self.assertIn("# Engineering Report", report_path.read_text(encoding="utf-8"))
            self.assertIn(plan_path, result.saved_files)
            self.assertIn(report_path, result.saved_files)
            self.assertTrue(any("[1/6] Extracting documents" in text for _, text in events))
            self.assertTrue(any("[4/6] Selecting compact evidence" in text for _, text in events))
            self.assertTrue(any("Timings:" in text for _, text in events))
            self.assertTrue(any("Saved" in text for _, text in events))
            self.assertTrue(any(kind == "markdown" for kind, _ in events))
            self.assertIn("total", result.timings)

    def test_generate_report_pipeline_reuses_empty_extraction_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            first = generate_report_pipeline(root, goal="Demo report")
            second = generate_report_pipeline(root, goal="Demo report")

            self.assertFalse(first.extraction_cache_used)
            self.assertTrue(second.extraction_cache_used)

    def test_generate_report_pipeline_fresh_bypasses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            generate_report_pipeline(root, goal="Demo report")
            second = generate_report_pipeline(root, goal="Demo report", force_refresh=True)

            self.assertFalse(second.extraction_cache_used)

    def test_generate_report_pipeline_excludes_generated_output_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "llm_result" / "document_pipeline"
            output_dir.mkdir(parents=True)
            (output_dir / "ignored.docx").write_bytes(b"not a real docx")

            result = generate_report_pipeline(root, goal="Demo report")

            self.assertEqual(result.documents, [])


if __name__ == "__main__":
    unittest.main()
