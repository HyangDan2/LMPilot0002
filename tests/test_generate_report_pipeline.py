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
            self.assertTrue(plan_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(json.loads(plan_path.read_text(encoding="utf-8"))["goal"], "Demo report")
            self.assertIn("# Workspace Report", report_path.read_text(encoding="utf-8"))
            self.assertIn(plan_path, result.saved_files)
            self.assertIn(report_path, result.saved_files)
            self.assertTrue(any("[1/6] Extracting documents" in text for _, text in events))
            self.assertTrue(any("[5/6] Selecting compact evidence" in text for _, text in events))
            self.assertTrue(any("Saved" in text for _, text in events))
            self.assertTrue(any(kind == "markdown" for kind, _ in events))


if __name__ == "__main__":
    unittest.main()
