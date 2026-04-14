from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunState:
    user_input: str
    provider_name: str = ""
    model_name: str = ""
    system_prompt: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)
    parsed_output: Any | None = None
    final_answer: str = ""
    error: str | None = None
    step_logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_log(self, message: str) -> None:
        self.step_logs.append(message)

    def set_error(self, message: str) -> None:
        self.error = message
        self.add_log(f"ERROR: {message}")
