from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .context import SlashToolContext
from .errors import SlashToolError
from .path_safety import output_root, require_working_folder
from .results import SlashToolResult


def save_last_output_command(
    args: list[str],
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress=None,
) -> SlashToolResult:
    if args:
        raise SlashToolError("Usage: /save_last_output")
    if context.last_output_getter is None:
        raise SlashToolError("No chat output provider is available.")

    root = require_working_folder(working_folder)
    output = context.last_output_getter().strip()
    if not output:
        raise SlashToolError("No assistant or tool output is available to save.")

    out_dir = output_root(root, "save_last_output")
    output_path = out_dir / f"{datetime.now().strftime('%y%m%d_%H%M%S')}.md"
    output_path.write_text(output + "\n", encoding="utf-8")
    return SlashToolResult(
        text=f"Last output saved:\n{output_path}",
        tool_name="/save_last_output",
    )
