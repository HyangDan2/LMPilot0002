from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import shlex
from typing import Any

from .calculator import CalculatorError, calculate
from .image_analyze import ImageAnalyzeError, build_image_analyze_content
from .use_file import UseFileError, build_use_file_prompt


class ToolError(Exception):
    pass


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class AttachedFileCommand:
    target: str
    instruction: str = ""


@dataclass(frozen=True)
class PromptToolResult:
    content: str | list[dict[str, Any]]
    selected_path: str
    instruction: str = ""


def _run_calculator(arguments: dict[str, Any]) -> str:
    expression = arguments.get("expression")
    if not isinstance(expression, str):
        raise ToolError("Calculator requires an expression string.")
    try:
        return calculate(expression)
    except CalculatorError as exc:
        raise ToolError(str(exc)) from exc


def _run_use_file(arguments: dict[str, Any]) -> str:
    path = arguments.get("path")
    paths = [path] if isinstance(path, str) else arguments.get("paths")
    instruction = arguments.get("instruction", "")
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise ToolError("use_file requires a list of file paths.")
    if not isinstance(instruction, str):
        raise ToolError("use_file instruction must be a string.")
    try:
        return build_use_file_prompt(paths, instruction)
    except UseFileError as exc:
        raise ToolError(str(exc)) from exc


def _run_image_analyze(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    path = arguments.get("path")
    instruction = arguments.get("instruction", "")
    if not isinstance(path, str):
        raise ToolError("image_analyze requires an image file path.")
    if not isinstance(instruction, str):
        raise ToolError("image_analyze instruction must be a string.")
    try:
        return build_image_analyze_content(path, instruction)
    except ImageAnalyzeError as exc:
        raise ToolError(str(exc)) from exc


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "calculator": {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression.",
        "parameters": {
            "expression": {
                "type": "string",
                "description": "Arithmetic expression, for example 2 + 3 * 4.",
            }
        },
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Evaluate a basic arithmetic expression.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Arithmetic expression, for example 2 + 3 * 4.",
                        }
                    },
                    "required": ["expression"],
                },
            },
        },
        "handler": _run_calculator,
    },
    "use_file": {
        "name": "use_file",
        "description": "Read one explicitly attached file and transform it into model prompt context.",
        "parameters": {
            "path": {
                "type": "string",
                "description": "Attached file path selected in the GUI.",
            },
            "instruction": {
                "type": "string",
                "description": "User instruction to ask over the file content.",
            },
        },
        "schema": {
            "type": "function",
            "function": {
                "name": "use_file",
                "description": "Read one explicitly attached file and transform it into model prompt context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Attached file path selected in the GUI.",
                        },
                        "instruction": {
                            "type": "string",
                            "description": "User instruction to ask over the file content.",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        "handler": _run_use_file,
    },
    "image_analyze": {
        "name": "image_analyze",
        "description": "Send one explicitly attached image to a vision-capable model with instructions.",
        "parameters": {
            "path": {
                "type": "string",
                "description": "Attached image file path selected in the GUI.",
            },
            "instruction": {
                "type": "string",
                "description": "User instruction to ask about the image.",
            },
        },
        "schema": {
            "type": "function",
            "function": {
                "name": "image_analyze",
                "description": "Send one explicitly attached image to a vision-capable model with instructions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Attached image file path selected in the GUI.",
                        },
                        "instruction": {
                            "type": "string",
                            "description": "User instruction to ask about the image.",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        "handler": _run_image_analyze,
    },
}


def list_tool_schemas() -> list[dict[str, Any]]:
    return [dict(tool["schema"]) for tool in TOOL_REGISTRY.values()]


def run_tool(name: str, arguments: dict[str, Any]) -> Any:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool: {name}")
    handler = tool.get("handler")
    if not callable(handler):
        raise ToolError(f"Tool is not executable: {name}")
    return handler(arguments)


def run_tool_command(command_text: str) -> str | None:
    text = command_text.strip()
    if not text.startswith("/"):
        return None
    command, _, argument_text = text[1:].partition(" ")
    if command.lower() not in {"calc", "calculator"}:
        return None
    return str(run_tool("calculator", {"expression": argument_text}))


def _parse_attached_file_command(command_text: str, command_name: str) -> AttachedFileCommand | None:
    text = command_text.strip()
    if not text.startswith("/"):
        return None
    command, _, _argument_text = text[1:].partition(" ")
    if command.lower() != command_name:
        return None
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ToolError(f"Malformed /{command_name} command: {exc}") from exc
    if len(parts) < 2:
        raise ToolError(f"/{command_name} requires an attached filename or path.")
    return AttachedFileCommand(target=parts[1], instruction=" ".join(parts[2:]).strip())


def parse_use_file_command(command_text: str) -> AttachedFileCommand | None:
    return _parse_attached_file_command(command_text, "use_file")


def parse_image_analyze_command(command_text: str) -> AttachedFileCommand | None:
    return _parse_attached_file_command(command_text, "image_analyze")


def select_attached_path(
    target: str,
    paths: list[str],
    *,
    allowed_extensions: set[str] | None = None,
    command_name: str = "use_file",
) -> str:
    if not paths:
        raise ToolError(f"Attach a file before using /{command_name}.")

    matches: list[str] = []
    target_path = Path(target).expanduser()
    target_text = str(target_path)
    target_resolved = str(target_path.resolve(strict=False)) if target_path.is_absolute() else ""
    target_has_separator = "/" in target or "\\" in target

    for path in paths:
        candidate = Path(path).expanduser()
        candidate_resolved = str(candidate.resolve(strict=False))
        candidate_text = str(candidate)
        if target in {path, candidate_text, candidate.name}:
            matches.append(candidate_resolved)
            continue
        if target_resolved and candidate_resolved == target_resolved:
            matches.append(candidate_resolved)
            continue
        if target_has_separator and candidate_resolved.endswith(target_text):
            matches.append(candidate_resolved)

    unique_matches = list(dict.fromkeys(matches))
    if not unique_matches:
        raise ToolError(f"Attached file not found: {target}")
    if len(unique_matches) > 1:
        raise ToolError(f"Multiple attached files matched {target}. Use the full path.")

    selected_path = unique_matches[0]
    if allowed_extensions is not None and Path(selected_path).suffix.lower() not in allowed_extensions:
        supported = " ".join(sorted(allowed_extensions))
        raise ToolError(f"/{command_name} requires one of these file types: {supported}.")
    return selected_path


def run_use_file_command(command_text: str, paths: list[str]) -> PromptToolResult | None:
    command = parse_use_file_command(command_text)
    if command is None:
        return None
    selected_path = select_attached_path(command.target, paths, command_name="use_file")
    content = run_tool("use_file", {"path": selected_path, "instruction": command.instruction})
    if not isinstance(content, str):
        raise ToolError("use_file returned an invalid prompt.")
    return PromptToolResult(content=content, selected_path=selected_path, instruction=command.instruction)


def run_image_analyze_command(command_text: str, paths: list[str]) -> PromptToolResult | None:
    from .image_analyze import IMAGE_ANALYZE_EXTENSIONS

    command = parse_image_analyze_command(command_text)
    if command is None:
        return None
    selected_path = select_attached_path(
        command.target,
        paths,
        allowed_extensions=IMAGE_ANALYZE_EXTENSIONS,
        command_name="image_analyze",
    )
    content = run_tool("image_analyze", {"path": selected_path, "instruction": command.instruction})
    if not isinstance(content, list):
        raise ToolError("image_analyze returned an invalid prompt.")
    return PromptToolResult(content=content, selected_path=selected_path, instruction=command.instruction)
