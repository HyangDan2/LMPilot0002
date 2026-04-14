from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

try:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

    PYDANTIC_AVAILABLE = True
except (ModuleNotFoundError, ImportError):
    BaseModel = object  # type: ignore[assignment]
    ConfigDict = None  # type: ignore[assignment]
    Field = None  # type: ignore[assignment]
    ValidationError = ValueError  # type: ignore[assignment]
    PYDANTIC_AVAILABLE = False


if PYDANTIC_AVAILABLE:

    class ModelAction(BaseModel):
        model_config = ConfigDict(extra="ignore")

        action: str = Field(default="answer")
        tool_name: str | None = None
        tool_input: dict[str, Any] = Field(default_factory=dict)
        answer: str = ""

        @field_validator("action")
        @classmethod
        def normalize_action(cls, value: str) -> str:
            normalized = str(value or "answer").strip().lower()
            return normalized or "answer"

else:

    @dataclass
    class ModelAction:
        action: str = "answer"
        tool_name: str | None = None
        tool_input: dict[str, Any] = field(default_factory=dict)
        answer: str = ""

        @classmethod
        def model_validate(cls, data: Any) -> "ModelAction":
            if not isinstance(data, dict):
                raise ValueError("Structured output must be a JSON object.")
            tool_input = data.get("tool_input", {})
            if tool_input is None:
                tool_input = {}
            if not isinstance(tool_input, dict):
                raise ValueError("tool_input must be an object.")
            tool_name = data.get("tool_name")
            if tool_name is not None and not isinstance(tool_name, str):
                raise ValueError("tool_name must be a string or null.")
            return cls(
                action=str(data.get("action") or "answer").strip().lower() or "answer",
                tool_name=tool_name,
                tool_input=tool_input,
                answer=str(data.get("answer") or ""),
            )


def parse_structured_output(raw_text: str) -> tuple[ModelAction | None, str | None]:
    candidate = _extract_json_candidate(raw_text)
    if candidate is None:
        return None, "No JSON object found in model output."
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON structured output: {exc}"
    try:
        return ModelAction.model_validate(data), None
    except (ValidationError, ValueError, TypeError) as exc:
        return None, f"Structured output validation failed: {exc}"


def _extract_json_candidate(raw_text: str) -> str | None:
    text = raw_text.strip()
    if not text:
        return None
    fenced = _strip_json_fence(text)
    if fenced.startswith("{"):
        try:
            _, end = json.JSONDecoder().raw_decode(fenced)
        except json.JSONDecodeError:
            return fenced
        return fenced[:end]
    start = fenced.find("{")
    if start < 0:
        return None
    try:
        _, end = json.JSONDecoder().raw_decode(fenced[start:])
    except json.JSONDecodeError:
        return fenced[start:]
    return fenced[start : start + end]


def _strip_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text
