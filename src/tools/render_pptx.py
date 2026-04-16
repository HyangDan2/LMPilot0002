from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.config import PipelineConfig, load_config
from app.ingestion.scanner import scan_supported_files
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


DEFAULT_RENDER_GOAL = "Create a concise presentation from the attached working folder documents."
DEFAULT_CONFIG_PATH = "config.yaml"
RENDER_USAGE = "Usage: /render_pptx"
REQUIRED_CONFIG_KEYS = ("base_url", "api_key", "model")


def run_render_pptx_command(
    argument_text: str,
    *,
    attached_folder: str | None = None,
    config_path: str = DEFAULT_CONFIG_PATH,
) -> str:
    """Run the render_pptx pipeline from the active attached folder."""

    if argument_text.strip():
        raise RenderPptxCommandError(f"/render_pptx takes no arguments. {RENDER_USAGE}")

    if attached_folder is None or not attached_folder.strip():
        raise RenderPptxCommandError("No attached working folder found. Attach a folder first.")

    working_folder = Path(attached_folder).expanduser().resolve()
    if not working_folder.exists():
        raise RenderPptxCommandError(f"Attached working folder does not exist: {working_folder}")
    if not working_folder.is_dir():
        raise RenderPptxCommandError(f"Attached working folder is not a directory: {working_folder}")

    if not scan_supported_files(
        working_folder,
        excluded_dirs={working_folder / "llm_result", working_folder / "llm_output"},
    ):
        raise RenderPptxCommandError(f"No supported input files found in working folder: {working_folder}")

    try:
        config = build_attached_folder_render_config(working_folder, config_path=config_path)
        result = render_pptx_pipeline(DEFAULT_RENDER_GOAL, config)
    except RenderPptxCommandError:
        raise
    except Exception as exc:
        raise RenderPptxCommandError(str(exc)) from exc

    lines = [
        "render_pptx complete.",
        f"Working folder: {config.working_dir}",
        f"Result folder: {config.normalized_dir}",
        f"Output folder: {config.output_dir}",
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


def build_attached_folder_render_config(
    working_folder: Path,
    *,
    config_path: str = DEFAULT_CONFIG_PATH,
) -> PipelineConfig:
    settings = load_render_settings_from_config(config_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PipelineConfig(
        working_dir=working_folder,
        normalized_dir=working_folder / "llm_result",
        output_dir=working_folder / "llm_output",
        output_filename=f"rendered_report_{timestamp}.pptx",
        llm_base_url=settings["base_url"],
        llm_api_key=settings["api_key"],
        llm_model=settings["model"],
        timeout=float(settings.get("timeout", 120.0)),
        verify_ssl=bool(settings.get("verify_ssl", True)),
        ca_bundle=str(settings.get("ca_bundle", "")).strip(),
    )


def load_render_settings_from_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise RenderPptxCommandError(f"{path} not found. Create config.yaml first.")

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw: dict[str, Any] = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise RenderPptxCommandError(f"Failed to parse {path}: {exc}") from exc
    except OSError as exc:
        raise RenderPptxCommandError(f"Failed to read {path}: {exc}") from exc

    key_aliases = {
        "base_url": ("base_url", "openai_base_url"),
        "api_key": ("api_key", "openai_api_key"),
        "model": ("model", "openai_model"),
    }
    missing_keys = [
        key
        for key, aliases in key_aliases.items()
        if not any(alias in raw for alias in aliases)
    ]
    if missing_keys:
        raise RenderPptxCommandError(f"config.yaml is missing required keys: {', '.join(missing_keys)}")

    values = {
        "base_url": str(raw.get("base_url", raw.get("openai_base_url", ""))).strip(),
        "api_key": str(raw.get("api_key", raw.get("openai_api_key", ""))),
        "model": str(raw.get("model", raw.get("openai_model", ""))).strip(),
        "timeout": raw.get("response_timeout", raw.get("timeout", 120.0)),
        "verify_ssl": _parse_bool(raw.get("verify_ssl", raw.get("ssl_verify", True))),
        "ca_bundle": str(raw.get("ca_bundle", raw.get("ssl_ca_bundle", ""))).strip(),
    }
    missing = [key for key in ("base_url", "model") if not values[key]]
    if missing:
        raise RenderPptxCommandError(f"config.yaml has empty required values: {', '.join(missing)}")
    return values


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def run_render_pptx_command_from_arguments(argument_text: str) -> str:
    """Legacy argument-driven entry point kept for internal compatibility."""

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
            "Legacy usage: /render_pptx [--working-dir data/working] [--output-dir data/outputs] "
            "Create a 7-slide executive summary"
        )
    return RenderPptxCommandOptions(goal=goal, **values)
