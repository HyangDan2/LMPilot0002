from __future__ import annotations

from pathlib import Path

from .errors import SlashToolError

RESULT_ROOT_NAME = "HD2_result"


def require_working_folder(working_folder: str | Path | None) -> Path:
    if working_folder is None:
        raise SlashToolError("Select a workspace folder before using this slash tool.")
    root = Path(working_folder).expanduser().resolve()
    if not root.exists():
        raise SlashToolError(f"Workspace folder does not exist: {root}")
    if not root.is_dir():
        raise SlashToolError(f"Workspace path is not a folder: {root}")
    return root


def resolve_inside(root: Path, raw_path: str) -> Path:
    if not raw_path.strip():
        raise SlashToolError("A file path is required.")
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SlashToolError("Path is outside the current workspace folder.")
    return resolved


def output_root(root: Path, name: str) -> Path:
    path = root / RESULT_ROOT_NAME / name
    path.mkdir(parents=True, exist_ok=True)
    return path
