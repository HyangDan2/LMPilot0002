import tempfile
import unittest
from pathlib import Path

from app.config import PipelineConfig
from app.ingestion.scanner import scan_supported_files
from app.planner.planner import PlannerError, parse_presentation_plan
from src.tools.render_pptx import (
    RenderPptxCommandError,
    build_attached_folder_render_config,
    parse_render_pptx_arguments,
    run_render_pptx_command,
)


class RenderPptxPipelineTests(unittest.TestCase):
    def test_scanner_finds_supported_files_recursively(self) -> None:
        root = Path(tempfile.mkdtemp())
        nested = root / "nested"
        nested.mkdir()
        docx = root / "brief.docx"
        pdf = nested / "report.pdf"
        pptx = nested / "slides.pptx"
        ignored = root / "notes.txt"
        docx.write_bytes(b"placeholder")
        pdf.write_bytes(b"placeholder")
        pptx.write_bytes(b"placeholder")
        ignored.write_text("skip", encoding="utf-8")

        self.assertEqual(scan_supported_files(root), [docx.resolve(), pdf.resolve(), pptx.resolve()])

    def test_scanner_skips_excluded_output_folders(self) -> None:
        root = Path(tempfile.mkdtemp())
        source = root / "brief.docx"
        output = root / "llm_output"
        output.mkdir()
        generated = output / "rendered_report_20260415_120000.pptx"
        source.write_bytes(b"placeholder")
        generated.write_bytes(b"placeholder")

        self.assertEqual(
            scan_supported_files(root, excluded_dirs={output}),
            [source.resolve()],
        )

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

    def test_render_pptx_rejects_public_arguments(self) -> None:
        with self.assertRaises(RenderPptxCommandError) as raised:
            run_render_pptx_command("Create a deck", attached_folder=".")

        self.assertIn("takes no arguments", str(raised.exception))
        self.assertIn("Usage: /render_pptx", str(raised.exception))

    def test_render_pptx_requires_attached_folder(self) -> None:
        with self.assertRaises(RenderPptxCommandError) as raised:
            run_render_pptx_command("")

        self.assertIn("No attached working folder found", str(raised.exception))

    def test_attached_folder_config_forces_child_output_paths(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        config_path = root / "config.yaml"
        config_path.write_text(
            "base_url: http://localhost:8000/v1\n"
            "api_key: ''\n"
            "model: local-model\n",
            encoding="utf-8",
        )

        config = build_attached_folder_render_config(root, config_path=str(config_path))

        self.assertIsInstance(config, PipelineConfig)
        self.assertEqual(config.working_dir, root)
        self.assertEqual(config.output_dir, root / "llm_output")
        self.assertEqual(config.normalized_dir, root / "llm_result")
        self.assertRegex(config.output_filename or "", r"^rendered_report_\d{8}_\d{6}\.pptx$")
        self.assertEqual(config.llm_base_url, "http://localhost:8000/v1")
        self.assertEqual(config.llm_api_key, "")
        self.assertEqual(config.llm_model, "local-model")
        self.assertTrue(config.verify_ssl)
        self.assertEqual(config.ca_bundle, "")

    def test_attached_folder_config_supports_ssl_options(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        config_path = root / "config.yaml"
        config_path.write_text(
            "base_url: https://localhost:8000/v1\n"
            "api_key: test\n"
            "model: local-model\n"
            "verify_ssl: false\n"
            "ca_bundle: /tmp/internal-ca.pem\n",
            encoding="utf-8",
        )

        config = build_attached_folder_render_config(root, config_path=str(config_path))

        self.assertFalse(config.verify_ssl)
        self.assertEqual(config.ca_bundle, "/tmp/internal-ca.pem")

    def test_attached_folder_config_requires_config_keys(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        config_path = root / "config.yaml"
        config_path.write_text("base_url: http://localhost:8000/v1\n", encoding="utf-8")

        with self.assertRaises(RenderPptxCommandError) as raised:
            build_attached_folder_render_config(root, config_path=str(config_path))

        self.assertIn("missing required keys", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
