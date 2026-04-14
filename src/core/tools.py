from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    function: Callable[[dict[str, Any]], Any]
    argument_schema: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec] | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolSpec) -> None:
        if not tool.name.strip():
            raise ValueError("Tool name cannot be empty.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool.function(arguments or {})

    def to_prompt_text(self) -> str:
        lines: list[str] = []
        for tool in self.list_tools():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def to_provider_schemas(self) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for tool in self.list_tools():
            if tool.argument_schema:
                schemas.append(dict(tool.argument_schema))
        return schemas


def build_default_tool_registry() -> ToolRegistry:
    from src.tools.registry import TOOL_REGISTRY

    registry = ToolRegistry()
    for name, tool_data in TOOL_REGISTRY.items():
        handler = tool_data.get("handler")
        if not callable(handler):
            continue
        registry.register(
            ToolSpec(
                name=name,
                description=str(tool_data.get("description", "")),
                function=handler,
                argument_schema=dict(tool_data.get("schema", {})),
            )
        )
    return registry
