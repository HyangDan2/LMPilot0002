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
        self.response = "## 요약\n\n대체로 통과입니다."

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
                "/evaluate_file a.xlsx b.xlsx 확인하라",
                root,
                SlashToolContext(llm_client=client),
            )

            assert result is not None
            self.assertTrue((root / "HD2_result" / "extract_docs" / "a.xlsx.md").exists())
            self.assertTrue((root / "HD2_result" / "extract_docs" / "b.xlsx.md").exists())
            report = root / "HD2_result" / "evaluate_file" / "a.xlsx__vs__b.xlsx.md"
            self.assertTrue(report.exists())
            self.assertIn("대체로 통과", report.read_text(encoding="utf-8"))
            self.assertEqual(len(client.messages), 1)
            self.assertIn("확인하라", client.messages[0][0]["content"])
            self.assertIn("Must include launch plan", client.messages[0][1]["content"])
            self.assertIn("Launch plan included", client.messages[0][1]["content"])

    def test_evaluate_file_normalizes_html_line_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "standard.md").write_text("# 기준", encoding="utf-8")
            (root / "target.md").write_text("# 대상", encoding="utf-8")
            client = FakeEvaluationClient()
            client.response = "첫 줄<br>둘째 줄<br/>셋째 줄<br />넷째 줄"

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
            self.assertIn("첫 줄\n둘째 줄\n셋째 줄\n넷째 줄", result.text)
            self.assertIn("첫 줄\n둘째 줄\n셋째 줄\n넷째 줄", report_text)

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

    def test_evaluate_file_uses_prompt_config_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as prompt_temp:
            root = Path(temp_dir)
            prompt_dir = Path(prompt_temp)
            (prompt_dir / "evaluate_file.md").write_text(
                "커스텀 평가 프롬프트\n기준={{standard_name}}\n대상={{target_name}}\n지시={{instruction}}",
                encoding="utf-8",
            )
            _write_workbook(root / "a.xlsx", [["Criterion"], ["Must include launch plan"]])
            _write_workbook(root / "b.xlsx", [["Content"], ["Launch plan included"]])
            client = FakeEvaluationClient()

            with patch("src.slash_tools.prompt_loader.DEFAULT_PROMPT_DIR", prompt_dir):
                result = run_slash_command(
                    "/evaluate_file a.xlsx b.xlsx 확인하라",
                    root,
                    SlashToolContext(llm_client=client),
                )

            assert result is not None
            self.assertIn("커스텀 평가 프롬프트", client.messages[0][0]["content"])
            self.assertIn("기준=a.xlsx", client.messages[0][0]["content"])
            self.assertIn("대상=b.xlsx", client.messages[0][0]["content"])
            self.assertIn("지시=확인하라", client.messages[0][0]["content"])

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
            criteria_rows = [line for line in standard_text.splitlines() if line.startswith("| ") and "문서에 " in line]
            self.assertEqual(len(criteria_rows), 10)
            self.assertIn("정량적 성능 결과", evaluation_text)
            self.assertIn("운영 및 배포 절차", evaluation_text)
            self.assertNotIn("보안 고려사항", evaluation_text)
            self.assertNotIn("장애 대응", evaluation_text)
            self.assertEqual(len(client.messages), 1)
            self.assertIn("Mock_Standard.md의 기준으로 Mock_Evaluation.md의 파일의 내용을 평가하라", client.messages[0][0]["content"])
            report = root / "HD2_result" / "evaluate_file" / "Mock_Standard.md__vs__Mock_Evaluation.md.md"
            self.assertTrue(report.exists())
            self.assertIn("평가 결과가 저장되었습니다", result.text)

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

    def test_use_file_normalizes_html_line_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown = root / "source.md"
            markdown.write_text("# Source", encoding="utf-8")
            client = FakeEvaluationClient()
            client.response = "요약 A<br>요약 B"

            result = run_slash_command("/use_file source.md", root, SlashToolContext(llm_client=client))

            assert result is not None
            saved = list((root / "HD2_result" / "use_file").glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertNotIn("<br", result.text.lower())
            self.assertNotIn("<br", saved[0].read_text(encoding="utf-8").lower())
            self.assertIn("요약 A\n요약 B", result.text)

    def test_use_file_uses_prompt_config_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as prompt_temp:
            root = Path(temp_dir)
            prompt_dir = Path(prompt_temp)
            (prompt_dir / "use_file.md").write_text(
                "커스텀 사용 프롬프트\n파일={{source_name}}\n지시={{instruction}}",
                encoding="utf-8",
            )
            _write_workbook(root / "a.xlsx", [["Metric", "Value"], ["Revenue", "42"]])
            client = FakeEvaluationClient()

            with patch("src.slash_tools.prompt_loader.DEFAULT_PROMPT_DIR", prompt_dir):
                result = run_slash_command("/use_file a.xlsx 요약하라", root, SlashToolContext(llm_client=client))

            assert result is not None
            self.assertIn("커스텀 사용 프롬프트", client.messages[0][0]["content"])
            self.assertIn("파일=a.xlsx", client.messages[0][0]["content"])
            self.assertIn("지시=요약하라", client.messages[0][0]["content"])

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
            self.assertIn("첨부된 작업 폴더 밖", result.text)


def _write_workbook(path: Path, rows: list[list[str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


if __name__ == "__main__":
    unittest.main()
