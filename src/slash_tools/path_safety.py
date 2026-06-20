from __future__ import annotations

from pathlib import Path

from .errors import SlashToolError

RESULT_ROOT_NAME = "HD2_result"


def require_working_folder(working_folder: str | Path | None) -> Path:
    if working_folder is None:
        raise SlashToolError("이 slash tool을 사용하기 전에 폴더를 첨부하세요.")
    root = Path(working_folder).expanduser().resolve()
    if not root.exists():
        raise SlashToolError(f"첨부된 폴더가 존재하지 않습니다: {root}")
    if not root.is_dir():
        raise SlashToolError(f"첨부된 경로가 폴더가 아닙니다: {root}")
    return root


def resolve_inside(root: Path, raw_path: str) -> Path:
    if not raw_path.strip():
        raise SlashToolError("파일 경로가 필요합니다.")
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SlashToolError("경로가 첨부된 작업 폴더 밖에 있습니다.")
    return resolved


def output_root(root: Path, name: str) -> Path:
    path = root / RESULT_ROOT_NAME / name
    path.mkdir(parents=True, exist_ok=True)
    return path
