from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .context import SlashToolContext
from .errors import SlashToolError
from .path_safety import output_root, require_working_folder
from .results import SlashToolResult, normalize_markdown_output


def save_last_output_command(
    args: list[str],
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress=None,
) -> SlashToolResult:
    if args:
        raise SlashToolError("사용법: /save_last_output")
    if context.last_output_getter is None:
        raise SlashToolError("저장할 출력 조회 기능을 사용할 수 없습니다.")

    root = require_working_folder(working_folder)
    output = normalize_markdown_output(context.last_output_getter()).strip()
    if not output:
        raise SlashToolError("저장할 assistant 또는 tool 출력이 없습니다.")

    out_dir = output_root(root, "save_last_output")
    output_path = out_dir / f"{datetime.now().strftime('%y%m%d_%H%M%S')}.md"
    output_path.write_text(output + "\n", encoding="utf-8")
    return SlashToolResult(
        text=f"마지막 출력이 저장되었습니다:\n{output_path}",
        tool_name="/save_last_output",
    )
