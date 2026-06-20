from __future__ import annotations

import re
from dataclasses import dataclass

HTML_LINE_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def normalize_markdown_output(text: str) -> str:
    return HTML_LINE_BREAK_RE.sub("\n", text)


@dataclass(frozen=True)
class SlashToolResult:
    text: str
    tool_name: str
    history_text: str | None = None

    def __post_init__(self) -> None:
        normalized_text = normalize_markdown_output(self.text)
        object.__setattr__(self, "text", normalized_text)
        if self.history_text is None:
            object.__setattr__(self, "history_text", normalized_text)
        else:
            object.__setattr__(self, "history_text", normalize_markdown_output(self.history_text))


def error_result(message: str, tool_name: str = "/unknown") -> SlashToolResult:
    return SlashToolResult(text=f"Tool error: {message}", tool_name=tool_name)
