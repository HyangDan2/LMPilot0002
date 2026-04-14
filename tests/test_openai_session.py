import unittest
from collections.abc import Iterator

from src.gemma_console_gui.console_session import ConsoleConfig, ConsoleSessionError, OpenAICompatibleSession
from src.gemma_console_gui.llm_client import ChatStreamChunk, LLMClientError


class FakeOpenAIClient:
    def __init__(self, chunks: list[ChatStreamChunk], error: LLMClientError | None = None) -> None:
        self.chunks = chunks
        self.error = error
        self.chat_completion_calls = 0

    def stream_chat_completion(self, messages: list[dict[str, str]]) -> Iterator[ChatStreamChunk]:
        yield from self.chunks
        if self.error is not None:
            raise self.error

    def chat_completion(self, messages: list[dict[str, str]]) -> str:
        self.chat_completion_calls += 1
        return "fallback answer"

    def close_active_request(self) -> None:
        pass


class OpenAICompatibleSessionTests(unittest.TestCase):
    def make_session(self, client: FakeOpenAIClient) -> OpenAICompatibleSession:
        session = OpenAICompatibleSession(
            ConsoleConfig(
                llama_cli_path="/unused",
                model_path="/unused",
                openai_base_url="http://localhost:1234/v1",
                openai_model="local-model",
            )
        )
        session._client = client  # type: ignore[assignment]
        return session

    def test_stream_failure_before_final_text_falls_back_to_non_streaming(self) -> None:
        client = FakeOpenAIClient(
            [ChatStreamChunk(kind="reasoning")],
            LLMClientError("AttributeError: 'NoneType' object has no attribute 'peek'"),
        )
        session = self.make_session(client)

        chunks = list(session.ask_stream("hello"))

        self.assertEqual(
            [(chunk.kind, chunk.text) for chunk in chunks],
            [("reasoning", ""), ("final", "fallback answer")],
        )
        self.assertEqual(client.chat_completion_calls, 1)

    def test_generation_stopped_does_not_fall_back_to_non_streaming(self) -> None:
        client = FakeOpenAIClient([], LLMClientError("Generation stopped."))
        session = self.make_session(client)

        with self.assertRaises(ConsoleSessionError) as raised:
            list(session.ask_stream("hello"))

        self.assertEqual(str(raised.exception), "Generation stopped.")
        self.assertEqual(client.chat_completion_calls, 0)


if __name__ == "__main__":
    unittest.main()
