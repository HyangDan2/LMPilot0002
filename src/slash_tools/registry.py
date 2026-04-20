from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .context import SlashToolContext
from .document_pipeline import (
    build_doc_map_command,
    chunk_sections_command,
    detect_file_type_command,
    extract_docs_command,
    extract_single_doc_command,
    normalize_text_command,
    read_file_info_command,
)
from .errors import SlashToolError
from .help import help_command


SlashHandler = Callable[[list[str], str | Path | None, SlashToolContext], str]


@dataclass(frozen=True)
class SlashTool:
    name: str
    summary: str
    usage: str
    handler: SlashHandler


SLASH_TOOLS: dict[str, SlashTool] = {
    "/help": SlashTool("/help", "Show available local slash tools.", "/help", help_command),
    "/detect_file_type": SlashTool(
        "/detect_file_type",
        "Detect file extension, MIME type, family, and confidence.",
        "/detect_file_type <path>",
        detect_file_type_command,
    ),
    "/read_file_info": SlashTool(
        "/read_file_info",
        "Show file size and SHA-256 hash.",
        "/read_file_info <path>",
        read_file_info_command,
    ),
    "/normalize_text": SlashTool(
        "/normalize_text",
        "Normalize whitespace and control characters.",
        "/normalize_text <text>",
        normalize_text_command,
    ),
    "/extract_single_doc": SlashTool(
        "/extract_single_doc",
        "Extract one document and auto-save JSON artifacts.",
        "/extract_single_doc <path>",
        extract_single_doc_command,
    ),
    "/extract_docs": SlashTool(
        "/extract_docs",
        "Extract all supported documents in the attached folder and auto-save JSON artifacts.",
        "/extract_docs",
        extract_docs_command,
    ),
    "/build_doc_map": SlashTool(
        "/build_doc_map",
        "Build and auto-save a structural document map.",
        "/build_doc_map",
        build_doc_map_command,
    ),
    "/chunk_sections": SlashTool(
        "/chunk_sections",
        "Build and auto-save retrieval chunks.",
        "/chunk_sections [--max-chars N]",
        chunk_sections_command,
    ),
}


def run_slash_command(
    command_text: str,
    working_folder: str | Path | None,
    context: SlashToolContext,
) -> str | None:
    stripped = command_text.strip()
    if not stripped.startswith("/"):
        return None
    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        return f"Tool error: malformed slash command: {exc}"
    if not parts:
        return None
    command = parts[0].lower()
    tool = SLASH_TOOLS.get(command)
    if tool is None:
        return f"Tool error: unknown slash command '{command}'. Run /help to see available commands."
    try:
        return tool.handler(parts[1:], working_folder, context)
    except SlashToolError as exc:
        return f"Tool error: {exc}"
    except Exception as exc:
        return f"Tool error: unexpected failure while running {command}: {exc}"
