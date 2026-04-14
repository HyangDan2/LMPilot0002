import unittest

from src.tools import ToolError, list_tool_schemas, run_tool, run_tool_command


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


if __name__ == "__main__":
    unittest.main()
