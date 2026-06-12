from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable, Protocol

from src.gui.llm_client import OpenAIConnectionSettings


class EvaluationClient(Protocol):
    def chat_completion(self, messages: list[dict], response_format: dict | None = None) -> str: ...
    def close_active_request(self) -> None: ...


@dataclass
class SlashToolContext:
    llm_settings: OpenAIConnectionSettings | None = None
    llm_client: EvaluationClient | None = None
    last_output_getter: Callable[[], str] | None = None
    cancel_event: Event | None = None

    def request_stop(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()
        if self.llm_client is not None:
            self.llm_client.close_active_request()

    def check_cancelled(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise RuntimeError("Slash tool cancelled.")
