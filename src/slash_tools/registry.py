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
        description="Extracts xlsx, pptx, pdf, and docx files into markdown under HD2_result/extract_docs.",
        usage="/extract_file <file>",
        handler=extract_file_command,
        examples=["/extract_file a.xlsx", "/extract_file 'deck review.pptx'"],
    ),
    "/evaluate_file": SlashTool(
        name="/evaluate_file",
        description="Evaluates a target markdown or source file against a standard markdown or source file with the LLM. Use --mock-test for a sample evaluation.",
        usage="/evaluate_file <standard markdown|file> <target markdown|file> [extra instruction] or /evaluate_file --mock-test",
        handler=evaluate_file_command,
        examples=["/evaluate_file a.xlsx b.pptx Check whether the content is properly structured.", "/evaluate_file --mock-test"],
    ),
    "/use_file": SlashTool(
        name="/use_file",
        description="Generates an LLM answer grounded in one markdown or source file. Extracts the file first when needed.",
        usage="/use_file <markdown|file> [instruction]",
        handler=use_file_command,
        examples=["/use_file a.xlsx Find and summarize the quantitative results in this file.", "/use_file a.xlsx"],
    ),
    "/save_last_output": SlashTool(
        name="/save_last_output",
        description="Saves the latest assistant or tool output under HD2_result/save_last_output.",
        usage="/save_last_output",
        handler=save_last_output_command,
        examples=["/save_last_output"],
    ),
    "/tool_help": SlashTool(
        name="/tool_help",
        description="Shows help for available local slash tools.",
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
        return error_result(f"Unknown slash command: '{command}'. Use /tool_help to see available commands.", command)
    try:
        return tool.handler(parts[1:], working_folder, context, progress)
    except SlashToolError as exc:
        return error_result(str(exc), command)
