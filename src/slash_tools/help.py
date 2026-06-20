from __future__ import annotations

from pathlib import Path

from .context import SlashToolContext
from .results import SlashToolResult


def tool_help_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext, progress=None) -> SlashToolResult:
    from .registry import SLASH_TOOLS

    lines = ["# 로컬 Slash Tools", ""]
    for tool in SLASH_TOOLS.values():
        lines.extend(
            [
                f"## {tool.name}",
                "",
                tool.description,
                "",
                f"사용법: `{tool.usage}`",
                "",
            ]
        )
        if tool.examples:
            lines.append("예시:")
            for example in tool.examples:
                lines.append(f"- `{example}`")
            lines.append("")
    return SlashToolResult(text="\n".join(lines).strip(), tool_name="/tool_help")
