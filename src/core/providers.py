from __future__ import annotations

from typing import Any, Protocol

from collections.abc import Iterator

from src.gemma_console_gui.llm_client import ChatStreamChunk, OpenAICompatibleClient


class BaseLLMProvider(Protocol):
    name: str
    model_name: str

    def generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        ...


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(self, client: OpenAICompatibleClient, model_name: str = "") -> None:
        self.client = client
        self.model_name = model_name

    def generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        return self.client.chat_completion(messages)

    def stream_generate(self, messages: list[dict[str, Any]], **kwargs: Any) -> Iterator[ChatStreamChunk]:
        return self.client.stream_chat_completion(messages)
