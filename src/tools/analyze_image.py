from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from src.gui.attachment_handler import IMAGE_EXTENSIONS, validate_attachment_path


DEFAULT_IMAGE_ANALYZE_INSTRUCTION = "Please analyze this image."
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}
IMAGE_ANALYZE_EXTENSIONS = IMAGE_EXTENSIONS


class AnalyzeImageError(Exception):
    pass


def build_analyze_image_content(path: str, instruction: str = "") -> list[dict[str, Any]]:
    try:
        image_path = validate_attachment_path(path)
    except Exception as exc:
        raise AnalyzeImageError(str(exc)) from exc

    suffix = image_path.suffix.lower()
    if suffix not in IMAGE_ANALYZE_EXTENSIONS:
        supported = " ".join(sorted(IMAGE_ANALYZE_EXTENSIONS))
        raise AnalyzeImageError(f"/analyze_image requires an image file ({supported}).")

    try:
        encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    except OSError as exc:
        raise AnalyzeImageError(f"Failed to read image file: {exc}") from exc

    prompt_instruction = instruction.strip() or DEFAULT_IMAGE_ANALYZE_INSTRUCTION
    mime_type = IMAGE_MIME_TYPES.get(suffix, "application/octet-stream")
    return [
        {"type": "text", "text": prompt_instruction},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
    ]
