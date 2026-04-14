import tempfile
import unittest
from pathlib import Path

from src.tools import (
    ToolError,
    list_tool_schemas,
    parse_analyze_image_command,
    run_analyze_image_command,
    parse_use_file_command,
    run_tool,
    run_tool_command,
    run_use_file_command,
    select_attached_path,
)


class ToolRegistryTests(unittest.TestCase):
    def test_calculator_command_runs_basic_arithmetic(self) -> None:
        self.assertEqual(run_tool_command("/calc 2 + 3 * 4"), "14")

    def test_calculator_command_allows_parentheses(self) -> None:
        self.assertEqual(run_tool_command("/calculator (2 + 3) * 4"), "20")

    def test_non_tool_command_is_ignored(self) -> None:
        self.assertIsNone(run_tool_command("regular prompt"))
        self.assertIsNone(run_tool_command("/unknown 1 + 1"))

    def test_calculator_rejects_unsafe_expression(self) -> None:
        with self.assertRaises(ToolError):
            run_tool("calculator", {"expression": "__import__('os').system('date')"})

    def test_tool_schema_is_available_for_future_tool_calls(self) -> None:
        schemas = list_tool_schemas()

        self.assertEqual(schemas[0]["type"], "function")
        self.assertEqual(schemas[0]["function"]["name"], "calculator")
        self.assertIn("analyze_image", {schema["function"]["name"] for schema in schemas})

    def test_use_file_command_transforms_prompt_with_attached_file_content(self) -> None:
        path = Path(tempfile.mkdtemp()) / "note.txt"
        path.write_text("hello attachment", encoding="utf-8")

        result = run_use_file_command("/use_file note.txt summarize this", [str(path)])

        self.assertIsNotNone(result)
        assert result is not None
        prompt = result.content
        self.assertEqual(Path(result.selected_path), path.resolve())
        self.assertIn("File name: note.txt", prompt)
        self.assertIn("hello attachment", prompt)
        self.assertTrue(prompt.endswith("User message:\nsummarize this"))

    def test_use_file_command_uses_slash_prefix(self) -> None:
        parsed = parse_use_file_command("/use_file note.txt summarize")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.target, "note.txt")
        self.assertEqual(parsed.instruction, "summarize")
        self.assertIsNone(parse_use_file_command("./use_file summarize"))
        self.assertIsNone(run_use_file_command("./use_file summarize", []))

    def test_use_file_command_requires_attached_paths(self) -> None:
        with self.assertRaises(ToolError):
            run_use_file_command("/use_file note.txt summarize", [])

    def test_use_file_command_selects_one_attached_file_by_name(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        note_path = temp_dir / "note.txt"
        other_path = temp_dir / "other.txt"
        note_path.write_text("selected text", encoding="utf-8")
        other_path.write_text("other text", encoding="utf-8")

        result = run_use_file_command("/use_file note.txt summarize this", [str(other_path), str(note_path)])

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(Path(result.selected_path), note_path.resolve())
        self.assertIn("selected text", result.content)
        self.assertNotIn("other text", result.content)

    def test_use_file_command_reports_duplicate_filenames(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        first = temp_dir / "a" / "note.txt"
        second = temp_dir / "b" / "note.txt"
        first.parent.mkdir()
        second.parent.mkdir()
        first.write_text("first", encoding="utf-8")
        second.write_text("second", encoding="utf-8")

        with self.assertRaises(ToolError) as raised:
            select_attached_path("note.txt", [str(first), str(second)], command_name="use_file")

        self.assertIn("Multiple attached files", str(raised.exception))

    def test_analyze_image_command_builds_openai_vision_content(self) -> None:
        path = Path(tempfile.mkdtemp()) / "photo.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\nsample")

        result = run_analyze_image_command("/analyze_image photo.png describe it", [str(path)])

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.instruction, "describe it")
        self.assertEqual(result.content[0], {"type": "text", "text": "describe it"})
        self.assertEqual(result.content[1]["type"], "image_url")
        self.assertTrue(result.content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_analyze_image_command_uses_named_target_and_instruction(self) -> None:
        parsed = parse_analyze_image_command("/analyze_image chart.png summarize trends")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.target, "chart.png")
        self.assertEqual(parsed.instruction, "summarize trends")

    def test_analyze_image_command_rejects_non_image_target(self) -> None:
        path = Path(tempfile.mkdtemp()) / "note.txt"
        path.write_text("not an image", encoding="utf-8")

        with self.assertRaises(ToolError):
            run_analyze_image_command("/analyze_image note.txt describe it", [str(path)])


if __name__ == "__main__":
    unittest.main()
