from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    llama_cli_path: str
    model_path: str
    backend: str = "server"
    server_url: str = "http://127.0.0.1:8080"
    server_endpoint: str = "auto"
    n_predict: int = 512
    system_prompt: str = "You are a helpful assistant."
    threads: int = 4
    ctx_size: int = 2048
    extra_args: list[str] = field(default_factory=list)
    startup_timeout: float = 180.0
    response_timeout: float = 180.0
    db_path: str = "./data/app.db"
    window_title: str = "Gemma Console GUI (PySide6)"
    window_width: int = 1000
    window_height: int = 720
    response_token_reserve: int = 256
    max_prompt_chars: int = 12000


def load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    return AppConfig(
        llama_cli_path=raw.get(
            "llama_cli_path",
            "/home/pi/Downloads/llama.cpp/build/bin/llama-cli",
        ),
        model_path=raw.get(
            "model_path",
            "/home/pi/.cache/huggingface/hub/models--ggml-org--gemma-3-1b-it-GGUF/snapshots/f9c28bcd85737ffc5aef028638d3341d49869c27/gemma-3-1b-it-Q4_K_M.gguf",
        ),
        backend=raw.get("backend", "server"),
        server_url=raw.get("server_url", "http://127.0.0.1:8080"),
        server_endpoint=raw.get("server_endpoint", "auto"),
        n_predict=int(raw.get("n_predict", 512)),
        system_prompt=raw.get("system_prompt", "You are a helpful assistant."),
        threads=int(raw.get("threads", 4)),
        ctx_size=int(raw.get("ctx_size", 2048)),
        extra_args=list(raw.get("extra_args", [])),
        startup_timeout=float(raw.get("startup_timeout", 180.0)),
        response_timeout=float(raw.get("response_timeout", 180.0)),
        db_path=raw.get("db_path", "./data/app.db"),
        window_title=raw.get("window_title", "Gemma Console GUI (PySide6)"),
        window_width=int(raw.get("window_width", 1000)),
        window_height=int(raw.get("window_height", 720)),
        response_token_reserve=int(raw.get("response_token_reserve", 256)),
        max_prompt_chars=int(raw.get("max_prompt_chars", 12000)),
    )
