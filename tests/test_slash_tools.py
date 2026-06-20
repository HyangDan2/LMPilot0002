import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from src.slash_tools import SlashToolContext, run_slash_command


class FakeEvaluationClient:
    def __init__(self) -> None:
        self.messages: list[list[dict]] = []
        self.closed = False
        self.response = "## Summary\n\nMostly passes."

    def chat_completion(self, messages: list[dict], response_format: dict | None = None) -> str:
        self.messages.append(messages)
        return self.response

    def close_active_request(self) -> None:
        self.closed = True


class SlashToolsTests(unittest.TestCase):
    def test_tool_help_is_registry_generated(self) -> None:
        result = run_slash_command("/tool_help", None, SlashToolContext())

        assert result is not None
        self.assertIn("/extract_file", result.text)
        self.assertIn("/evaluate_file", result.text)
        self.assertIn("/use_file", result.text)
        self.assertIn("/save_last_output", result.text)
        self.assertIn("/tool_help", result.text)
        self.assertIn("--mock-test", result.text)

    def test_extract_file_writes_xlsx_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workbook_path = root / "a.xlsx"
            _write_workbook(workbook_path, [["Criterion", "Value"], ["Speed", "Fast"]])

            result = run_slash_command("/extract_file a.xlsx", root, SlashToolContext())

            assert result is not None
            output_path = root / "HD2_result" / "extract_docs" / "a.xlsx.md"
            self.assertTrue(output_path.exists())
            text = output_path.read_text(encoding="utf-8")
            self.assertIn("# Extracted: a.xlsx", text)
            self.assertIn("Speed", text)
            self.assertIn(str(output_path), result.text)

    def test_evaluate_file_extracts_prerequisites_and_calls_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            standard = root / "a.xlsx"
            target = root / "b.xlsx"
            _write_workbook(standard, [["Criterion"], ["Must include launch plan"]])
            _write_workbook(target, [["Content"], ["Launch plan included"]])
            client = FakeEvaluationClient()

            result = run_slash_command(
                "/evaluate_file a.xlsx b.xlsx Check this.",
                root,
                SlashToolContext(llm_client=client),
            )

            assert result is not None
            self.assertTrue((root / "HD2_result" / "extract_docs" / "a.xlsx.md").exists())
            self.assertTrue((root / "HD2_result" / "extract_docs" / "b.xlsx.md").exists())
            report = root / "HD2_result" / "evaluate_file" / "a.xlsx__vs__b.xlsx.md"
            self.assertTrue(report.exists())
            self.assertIn("Mostly passes", report.read_text(encoding="utf-8"))
            self.assertEqual(len(client.messages), 1)
            self.assertIn("Check this.", client.messages[0][0]["content"])
            self.assertIn("Must include launch plan", client.messages[0][1]["content"])
            self.assertIn("Launch plan included", client.messages[0][1]["content"])

    def test_evaluate_file_normalizes_html_line_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "standard.md").write_text("# Standard", encoding="utf-8")
            (root / "target.md").write_text("# Target", encoding="utf-8")
            client = FakeEvaluationClient()
            client.response = "first line<br>second line<br/>third line<br />fourth line"

            result = run_slash_command(
                "/evaluate_file standard.md target.md",
                root,
                SlashToolContext(llm_client=client),
            )

            assert result is not None
            report = root / "HD2_result" / "evaluate_file" / "standard.md__vs__target.md.md"
            report_text = report.read_text(encoding="utf-8")
            self.assertNotIn("<br", result.text.lower())
            self.assertNotIn("<br", report_text.lower())
            self.assertIn("first line\nsecond line\nthird line\nfourth line", result.text)
            self.assertIn("first line\nsecond line\nthird line\nfourth line", report_text)

    def test_evaluate_file_uses_default_prompt_when_instruction_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workbook(root / "a.xlsx", [["Criterion"], ["Must include launch plan"]])
            _write_workbook(root / "b.xlsx", [["Content"], ["Launch plan included"]])
            client = FakeEvaluationClient()

            result = run_slash_command(
                "/evaluate_file a.xlsx b.xlsx",
                root,
                SlashToolContext(llm_client=client),
            )

            assert result is not None
            self.assertIn("Evaluate the content of b.xlsx using a.xlsx as the standard.", client.messages[0][0]["content"])

    def test_evaluate_file_uses_prompt_config_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as prompt_temp:
            root = Path(temp_dir)
            prompt_dir = Path(prompt_temp)
            (prompt_dir / "evaluate_file.md").write_text(
                "Custom evaluation prompt\nstandard={{standard_name}}\ntarget={{target_name}}\ninstruction={{instruction}}",
                encoding="utf-8",
            )
            _write_workbook(root / "a.xlsx", [["Criterion"], ["Must include launch plan"]])
            _write_workbook(root / "b.xlsx", [["Content"], ["Launch plan included"]])
            client = FakeEvaluationClient()

            with patch("src.slash_tools.prompt_loader.DEFAULT_PROMPT_DIR", prompt_dir):
                result = run_slash_command(
                    "/evaluate_file a.xlsx b.xlsx Check this.",
                    root,
                    SlashToolContext(llm_client=client),
                )

            assert result is not None
            self.assertIn("Custom evaluation prompt", client.messages[0][0]["content"])
            self.assertIn("standard=a.xlsx", client.messages[0][0]["content"])
            self.assertIn("target=b.xlsx", client.messages[0][0]["content"])
            self.assertIn("instruction=Check this.", client.messages[0][0]["content"])

    def test_evaluate_file_mock_test_creates_files_and_runs_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = FakeEvaluationClient()

            result = run_slash_command("/evaluate_file --mock-test", root, SlashToolContext(llm_client=client))

            assert result is not None
            standard = root / "Mock_Standard.md"
            evaluation = root / "Mock_Evaluation.md"
            self.assertTrue(standard.exists())
            self.assertTrue(evaluation.exists())
            standard_text = standard.read_text(encoding="utf-8")
            evaluation_text = evaluation.read_text(encoding="utf-8")
            criteria_rows = [line for line in standard_text.splitlines() if line.startswith("| ") and "Does the document" in line]
            self.assertEqual(len(criteria_rows), 10)
            self.assertIn("Quantitative Performance Results", evaluation_text)
            self.assertIn("Operations and Deployment Procedures", evaluation_text)
            self.assertNotIn("Security Considerations", evaluation_text)
            self.assertNotIn("Incident Response", evaluation_text)
            self.assertEqual(len(client.messages), 1)
            self.assertIn("Evaluate the content of Mock_Evaluation.md using Mock_Standard.md as the standard.", client.messages[0][0]["content"])
            report = root / "HD2_result" / "evaluate_file" / "Mock_Standard.md__vs__Mock_Evaluation.md.md"
            self.assertTrue(report.exists())
            self.assertIn("Evaluation result saved", result.text)

    def test_use_file_extracts_then_calls_llm_with_default_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workbook(root / "a.xlsx", [["Metric", "Value"], ["Revenue", "42"]])
            client = FakeEvaluationClient()

            result = run_slash_command("/use_file a.xlsx", root, SlashToolContext(llm_client=client))

            assert result is not None
            self.assertTrue((root / "HD2_result" / "extract_docs" / "a.xlsx.md").exists())
            saved = list((root / "HD2_result" / "use_file").glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertIn("Summarize the content of a.xlsx.", client.messages[0][1]["content"])
            self.assertIn("Revenue", client.messages[0][1]["content"])

    def test_use_file_normalizes_html_line_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown = root / "source.md"
            markdown.write_text("# Source", encoding="utf-8")
            client = FakeEvaluationClient()
            client.response = "summary A<br>summary B"

            result = run_slash_command("/use_file source.md", root, SlashToolContext(llm_client=client))

            assert result is not None
            saved = list((root / "HD2_result" / "use_file").glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertNotIn("<br", result.text.lower())
            self.assertNotIn("<br", saved[0].read_text(encoding="utf-8").lower())
            self.assertIn("summary A\nsummary B", result.text)

    def test_use_file_uses_prompt_config_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as prompt_temp:
            root = Path(temp_dir)
            prompt_dir = Path(prompt_temp)
            (prompt_dir / "use_file.md").write_text(
                "Custom use prompt\nfile={{source_name}}\ninstruction={{instruction}}",
                encoding="utf-8",
            )
            _write_workbook(root / "a.xlsx", [["Metric", "Value"], ["Revenue", "42"]])
            client = FakeEvaluationClient()

            with patch("src.slash_tools.prompt_loader.DEFAULT_PROMPT_DIR", prompt_dir):
                result = run_slash_command("/use_file a.xlsx Summarize it.", root, SlashToolContext(llm_client=client))

            assert result is not None
            self.assertIn("Custom use prompt", client.messages[0][0]["content"])
            self.assertIn("file=a.xlsx", client.messages[0][0]["content"])
            self.assertIn("instruction=Summarize it.", client.messages[0][0]["content"])

    def test_save_last_output_writes_timestamped_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = run_slash_command(
                "/save_last_output",
                root,
                SlashToolContext(last_output_getter=lambda: "latest answer"),
            )

            assert result is not None
            saved = list((root / "HD2_result" / "save_last_output").glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertRegex(saved[0].name, r"^\d{6}_\d{6}\.md$")
            self.assertEqual(saved[0].read_text(encoding="utf-8"), "latest answer\n")

    def test_save_last_output_normalizes_html_line_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = run_slash_command(
                "/save_last_output",
                root,
                SlashToolContext(last_output_getter=lambda: "first<br>second"),
            )

            assert result is not None
            saved = list((root / "HD2_result" / "save_last_output").glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_text(encoding="utf-8"), "first\nsecond\n")

    def test_use_file_requires_chunk_retrieval_for_large_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown = root / "large.md"
            markdown.write_text("x" * 120_001, encoding="utf-8")
            client = FakeEvaluationClient()

            result = run_slash_command("/use_file large.md", root, SlashToolContext(llm_client=client))

            assert result is not None
            self.assertIn("Require chunk retrieval!", result.text)
            self.assertEqual(client.messages, [])

    def test_evaluate_file_requires_chunk_retrieval_for_large_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            standard = root / "standard.md"
            target = root / "target.md"
            standard.write_text("criteria", encoding="utf-8")
            target.write_text("x" * 120_001, encoding="utf-8")
            client = FakeEvaluationClient()

            result = run_slash_command("/evaluate_file standard.md target.md", root, SlashToolContext(llm_client=client))

            assert result is not None
            self.assertIn("Require chunk retrieval!", result.text)
            self.assertEqual(client.messages, [])

    def test_rejects_paths_outside_attached_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = run_slash_command("/extract_file ../secret.xlsx", root, SlashToolContext())

            assert result is not None
            self.assertIn("outside the current workspace folder", result.text)


def _write_workbook(path: Path, rows: list[list[str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


if __name__ == "__main__":
    unittest.main()
