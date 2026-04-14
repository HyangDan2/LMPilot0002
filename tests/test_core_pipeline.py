import unittest
from typing import Any

from src.core.pipeline import run_pipeline
from src.core.schemas import parse_structured_output
from src.core.state import RunState
from src.core.tools import ToolRegistry, ToolSpec, build_default_tool_registry


class FakeProvider:
    name = "fake"
    model_name = "fake-model"

    def __init__(self, output: str) -> None:
        self.output = output
        self.messages: list[dict[str, Any]] = []

    def generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.messages = messages
        return self.output


class CorePipelineTests(unittest.TestCase):
    def test_run_state_logs_and_errors(self) -> None:
        state = RunState(user_input="hello")

        state.add_log("prepare")
        state.set_error("failed")

        self.assertEqual(state.step_logs[0], "prepare")
        self.assertEqual(state.error, "failed")
        self.assertIn("ERROR: failed", state.step_logs)

    def test_tool_registry_lookup_and_execution(self) -> None:
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="echo",
                description="Echo text.",
                function=lambda arguments: arguments["text"],
                argument_schema={"name": "echo"},
            )
        )

        self.assertTrue(registry.has("echo"))
        self.assertEqual(registry.get("echo").description, "Echo text.")  # type: ignore[union-attr]
        self.assertEqual(registry.execute("echo", {"text": "ok"}), "ok")
        self.assertIn("echo", registry.to_prompt_text())
        self.assertEqual(registry.to_provider_schemas(), [{"name": "echo"}])

    def test_default_registry_adapts_existing_tools(self) -> None:
        registry = build_default_tool_registry()

        self.assertTrue(registry.has("calculator"))
        self.assertTrue(registry.has("use_file"))

    def test_structured_output_parser_accepts_answer_json(self) -> None:
        parsed, error = parse_structured_output('{"action":"answer","answer":"done"}')

        self.assertIsNone(error)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.action, "answer")
        self.assertEqual(parsed.answer, "done")

    def test_structured_output_parser_falls_back_gracefully(self) -> None:
        parsed, error = parse_structured_output("plain answer")

        self.assertIsNone(parsed)
        self.assertIn("No JSON object", error or "")

    def test_run_pipeline_preserves_plain_text_answer(self) -> None:
        provider = FakeProvider("plain answer")
        state = run_pipeline(RunState(user_input="hello"), provider, ToolRegistry())

        self.assertIsNone(state.error)
        self.assertEqual(state.final_answer, "plain answer")
        self.assertEqual(provider.messages[-1], {"role": "user", "content": "hello"})
        self.assertIn("structured_parse_error", state.metadata)

    def test_run_pipeline_uses_structured_answer_when_present(self) -> None:
        provider = FakeProvider('{"action":"answer","answer":"structured answer"}')
        state = run_pipeline(RunState(user_input="hello"), provider, ToolRegistry())

        self.assertIsNone(state.error)
        self.assertEqual(state.final_answer, "structured answer")
        self.assertIsNotNone(state.parsed_output)


if __name__ == "__main__":
    unittest.main()
