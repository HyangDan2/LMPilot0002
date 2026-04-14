from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .calculator import CalculatorError, calculate


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
    }
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
