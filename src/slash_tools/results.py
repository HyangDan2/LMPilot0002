from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashToolResult:
    text: str
    tool_name: str
    history_text: str | None = None

    def __post_init__(self) -> None:
        if self.history_text is None:
            object.__setattr__(self, "history_text", self.text)


def error_result(message: str, tool_name: str = "/unknown") -> SlashToolResult:
    return SlashToolResult(text=f"Tool error: {message}", tool_name=tool_name)
