import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from src.slash_tools import SlashToolContext, run_slash_command


class FakeEvaluationClient:
    def __init__(self) -> None:
        self.messages: list[list[dict]] = []
        self.closed = False

    def chat_completion(self, messages: list[dict], response_format: dict | None = None) -> str:
        self.messages.append(messages)
        return "## Summary\n\nPASS with notes."

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
                "/evaluate_file a.xlsx b.xlsx 확인하라",
                root,
                SlashToolContext(llm_client=client),
            )

            assert result is not None
            self.assertTrue((root / "HD2_result" / "extract_docs" / "a.xlsx.md").exists())
            self.assertTrue((root / "HD2_result" / "extract_docs" / "b.xlsx.md").exists())
            report = root / "HD2_result" / "evaluate_file" / "a.xlsx__vs__b.xlsx.md"
            self.assertTrue(report.exists())
            self.assertIn("PASS with notes", report.read_text(encoding="utf-8"))
            self.assertEqual(len(client.messages), 1)
            self.assertIn("확인하라", client.messages[0][0]["content"])
            self.assertIn("Must include launch plan", client.messages[0][1]["content"])
            self.assertIn("Launch plan included", client.messages[0][1]["content"])

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
            self.assertIn("a.xlsx의 기준으로 b.xlsx의 파일의 내용을 평가하라", client.messages[0][0]["content"])

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
            self.assertIn("a.xlsx의 내용을 요약하라", client.messages[0][1]["content"])
            self.assertIn("Revenue", client.messages[0][1]["content"])

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

    def test_rejects_paths_outside_attached_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = run_slash_command("/extract_file ../secret.xlsx", root, SlashToolContext())

            assert result is not None
            self.assertIn("outside the attached working folder", result.text)


def _write_workbook(path: Path, rows: list[list[str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


if __name__ == "__main__":
    unittest.main()
