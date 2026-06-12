from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .context import SlashToolContext
from .errors import SlashToolError
from .evaluate_file import evaluate_file_command
from .extract_file import extract_file_command
from .help import tool_help_command
from .save_last_output import save_last_output_command
from .use_file import use_file_command
from .results import SlashToolResult, error_result


SlashProgressCallback = Callable[[str, str], None]
SlashHandler = Callable[[list[str], str | Path | None, SlashToolContext, SlashProgressCallback | None], SlashToolResult]


@dataclass(frozen=True)
class SlashTool:
    name: str
    description: str
    usage: str
    handler: SlashHandler
    examples: list[str] = field(default_factory=list)


SLASH_TOOLS: dict[str, SlashTool] = {
    "/extract_file": SlashTool(
        name="/extract_file",
        description="Extract an xlsx, pptx, pdf, or docx file into markdown under HD2_result/extract_docs.",
        usage="/extract_file <file>",
        handler=extract_file_command,
        examples=["/extract_file a.xlsx", "/extract_file 'deck review.pptx'"],
    ),
    "/evaluate_file": SlashTool(
        name="/evaluate_file",
        description="Evaluate a target markdown or source file against a standard markdown or source file using the configured LLM.",
        usage="/evaluate_file <standard markdown|file> <target markdown|file> [extra prompt]",
        handler=evaluate_file_command,
        examples=["/evaluate_file a.xlsx b.pptx 해당 내용이 제대로 구성되어 있는지 확인하라"],
    ),
    "/use_file": SlashTool(
        name="/use_file",
        description="Ask the configured LLM to answer from one markdown or source file, extracting it first when needed.",
        usage="/use_file <markdown|file> [instruction]",
        handler=use_file_command,
        examples=["/use_file a.xlsx 해당 파일에서 quantitative result를 찾아서 요약하라", "/use_file a.xlsx"],
    ),
    "/save_last_output": SlashTool(
        name="/save_last_output",
        description="Save the latest assistant or tool output to HD2_result/save_last_output.",
        usage="/save_last_output",
        handler=save_last_output_command,
        examples=["/save_last_output"],
    ),
    "/tool_help": SlashTool(
        name="/tool_help",
        description="Show registry-generated help for all available local slash tools.",
        usage="/tool_help",
        handler=tool_help_command,
        examples=["/tool_help"],
    ),
}


def run_slash_command(
    command_text: str,
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress: SlashProgressCallback | None = None,
) -> SlashToolResult | None:
    stripped = command_text.strip()
    if not stripped.startswith("/"):
        return None
    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        return error_result(f"malformed slash command: {exc}")
    if not parts:
        return None
    command = parts[0]
    tool = SLASH_TOOLS.get(command)
    if tool is None:
        return error_result(f"unknown slash command '{command}'. Run /tool_help to see available commands.", command)
    try:
        return tool.handler(parts[1:], working_folder, context, progress)
    except SlashToolError as exc:
        return error_result(str(exc), command)
