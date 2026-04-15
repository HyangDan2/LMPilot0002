from __future__ import annotations

import shlex
from dataclasses import dataclass

from app.config import load_config
from app.main import render_pptx_pipeline


class RenderPptxCommandError(Exception):
    """Raised when /render_pptx cannot run."""


@dataclass(frozen=True)
class RenderPptxCommandOptions:
    goal: str
    working_dir: str | None = None
    normalized_dir: str | None = None
    output_dir: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None


def run_render_pptx_command(argument_text: str) -> str:
    """Run the render_pptx pipeline from a slash-command argument string."""

    options = parse_render_pptx_arguments(argument_text)
    config = load_config(
        working_dir=options.working_dir,
        normalized_dir=options.normalized_dir,
        output_dir=options.output_dir,
        llm_base_url=options.base_url,
        llm_api_key=options.api_key,
        llm_model=options.model,
    )
    try:
        result = render_pptx_pipeline(options.goal, config)
    except Exception as exc:
        raise RenderPptxCommandError(str(exc)) from exc

    lines = [
        "render_pptx complete.",
        f"Scanned files: {result.scanned_files}",
        f"Parsed documents: {result.parsed_documents}",
        f"Knowledge map: {result.knowledge_map_md}",
        f"Knowledge map JSON: {result.knowledge_map_json}",
        f"Planner JSON: {result.planner_json}",
        f"Output PPTX: {result.output_pptx}",
    ]
    if result.parse_errors:
        lines.append(f"Skipped files: {len(result.parse_errors)}")
    return "\n".join(lines)


def parse_render_pptx_arguments(argument_text: str) -> RenderPptxCommandOptions:
    """Parse simple GNU-style options followed by the free-form goal."""

    try:
        tokens = shlex.split(argument_text)
    except ValueError as exc:
        raise RenderPptxCommandError(f"Malformed /render_pptx command: {exc}") from exc

    values: dict[str, str] = {}
    goal_parts: list[str] = []
    index = 0
    option_names = {
        "--working-dir": "working_dir",
        "--normalized-dir": "normalized_dir",
        "--output-dir": "output_dir",
        "--base-url": "base_url",
        "--api-key": "api_key",
        "--model": "model",
    }
    while index < len(tokens):
        token = tokens[index]
        if token in option_names:
            if index + 1 >= len(tokens):
                raise RenderPptxCommandError(f"{token} requires a value.")
            values[option_names[token]] = tokens[index + 1]
            index += 2
            continue
        goal_parts.extend(tokens[index:])
        break

    goal = " ".join(goal_parts).strip()
    if not goal:
        raise RenderPptxCommandError(
            "Usage: /render_pptx [--working-dir data/working] [--output-dir data/outputs] "
            "Create a 7-slide executive summary"
        )
    return RenderPptxCommandOptions(goal=goal, **values)

