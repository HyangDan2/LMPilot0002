import tempfile
import unittest
from pathlib import Path

from src.tools import (
    ToolError,
    list_tool_schemas,
    parse_use_file_command,
    run_tool,
    run_tool_command,
    run_use_file_command,
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

    def test_use_file_command_transforms_prompt_with_attached_file_content(self) -> None:
        path = Path(tempfile.mkdtemp()) / "note.txt"
        path.write_text("hello attachment", encoding="utf-8")

        prompt = run_use_file_command("./use_file summarize this", [str(path)])

        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertIn("File name: note.txt", prompt)
        self.assertIn("hello attachment", prompt)
        self.assertTrue(prompt.endswith("User message:\nsummarize this"))

    def test_use_file_command_requires_explicit_dot_slash_prefix(self) -> None:
        self.assertIsNone(parse_use_file_command("/use_file summarize"))
        self.assertIsNone(run_use_file_command("/use_file summarize", []))

    def test_use_file_command_requires_attached_paths(self) -> None:
        with self.assertRaises(ToolError):
            run_use_file_command("./use_file summarize", [])


if __name__ == "__main__":
    unittest.main()
