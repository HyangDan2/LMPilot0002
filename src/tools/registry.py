from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .calculator import CalculatorError, calculate
from .use_file import UseFileError, build_use_file_prompt


class ToolError(Exception):
    pass


ToolHandler = Callable[[dict[str, Any]], str]


def _run_calculator(arguments: dict[str, Any]) -> str:
    expression = arguments.get("expression")
    if not isinstance(expression, str):
        raise ToolError("Calculator requires an expression string.")
    try:
        return calculate(expression)
    except CalculatorError as exc:
        raise ToolError(str(exc)) from exc


def _run_use_file(arguments: dict[str, Any]) -> str:
    paths = arguments.get("paths")
    instruction = arguments.get("instruction", "")
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise ToolError("use_file requires a list of file paths.")
    if not isinstance(instruction, str):
        raise ToolError("use_file instruction must be a string.")
    try:
        return build_use_file_prompt(paths, instruction)
    except UseFileError as exc:
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
        "description": "Read explicitly attached files and transform them into model prompt context.",
        "parameters": {
            "paths": {
                "type": "array",
                "description": "Attached file paths selected in the GUI.",
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
                "description": "Read explicitly attached files and transform them into model prompt context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Attached file paths selected in the GUI.",
                        },
                        "instruction": {
                            "type": "string",
                            "description": "User instruction to ask over the file content.",
                        },
                    },
                    "required": ["paths"],
                },
            },
        },
        "handler": _run_use_file,
    },
}


def list_tool_schemas() -> list[dict[str, Any]]:
    return [dict(tool["schema"]) for tool in TOOL_REGISTRY.values()]


def run_tool(name: str, arguments: dict[str, Any]) -> str:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool: {name}")
    handler = tool.get("handler")
    if not callable(handler):
        raise ToolError(f"Tool is not executable: {name}")
    return str(handler(arguments))


def run_tool_command(command_text: str) -> str | None:
    text = command_text.strip()
    if not text.startswith("/"):
        return None
    command, _, argument_text = text[1:].partition(" ")
    if command.lower() not in {"calc", "calculator"}:
        return None
    return run_tool("calculator", {"expression": argument_text})


def parse_use_file_command(command_text: str) -> str | None:
    text = command_text.strip()
    if not text.startswith("./"):
        return None
    command, _, argument_text = text[2:].partition(" ")
    if command.lower() != "use_file":
        return None
    return argument_text.strip()


def run_use_file_command(command_text: str, paths: list[str]) -> str | None:
    instruction = parse_use_file_command(command_text)
    if instruction is None:
        return None
    return run_tool("use_file", {"paths": paths, "instruction": instruction})
