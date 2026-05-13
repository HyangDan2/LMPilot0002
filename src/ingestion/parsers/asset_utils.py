from __future__ import annotations

import mimetypes
import posixpath
from pathlib import Path

from src.document_pipeline.low_level.file_io import compute_content_hash


def guess_mime_type(path: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "application/octet-stream"


def write_asset_file(
    asset_output_dir: Path | None,
    document_id: str,
    asset_id: str,
    source_name: str,
    data: bytes,
) -> tuple[str, str]:
    sha256 = compute_content_hash(data)
    if asset_output_dir is None:
        return "", sha256

    suffix = Path(source_name).suffix or ".bin"
    document_dir = asset_output_dir / document_id
    document_dir.mkdir(parents=True, exist_ok=True)
    output_path = document_dir / f"{asset_id}{suffix.lower()}"
    output_path.write_bytes(data)
    return str(output_path.resolve()), sha256


def resolve_ooxml_target(base_part: str, target: str) -> str:
    base_dir = posixpath.dirname(base_part)
    return posixpath.normpath(posixpath.join(base_dir, target))
