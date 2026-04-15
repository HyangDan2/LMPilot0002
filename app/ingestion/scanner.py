from __future__ import annotations

from pathlib import Path


SUPPORTED_EXTENSIONS = {".pptx", ".docx", ".xlsx", ".pdf"}


def scan_supported_files(root: Path) -> list[Path]:
    """Recursively scan root for supported document files."""

    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Working directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Working path is not a directory: {root}")

    files = [
        path.resolve()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS and not path.name.startswith("~$")
    ]
    return sorted(files, key=lambda path: str(path).lower())

