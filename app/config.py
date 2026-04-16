from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime configuration for the render_pptx workspace pipeline."""

    working_dir: Path
    normalized_dir: Path
    output_dir: Path
    output_filename: str | None = None
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    timeout: float = 120.0


def load_config(
    *,
    working_dir: str | None = None,
    normalized_dir: str | None = None,
    output_dir: str | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
) -> PipelineConfig:
    """Load configuration from explicit values first, then environment variables."""

    return PipelineConfig(
        working_dir=Path(working_dir or os.environ.get("WORKING_DIR", "data/working")),
        normalized_dir=Path(normalized_dir or os.environ.get("NORMALIZED_DIR", "data/normalized")),
        output_dir=Path(output_dir or os.environ.get("OUTPUT_DIR", "data/outputs")),
        output_filename=None,
        llm_base_url=llm_base_url or os.environ.get("LLM_BASE_URL", ""),
        llm_api_key=llm_api_key or os.environ.get("LLM_API_KEY", ""),
        llm_model=llm_model or os.environ.get("LLM_MODEL", ""),
        timeout=float(os.environ.get("LLM_TIMEOUT", "120")),
    )
