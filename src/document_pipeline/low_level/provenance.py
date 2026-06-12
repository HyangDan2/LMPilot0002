from __future__ import annotations

from pathlib import Path

from src.document_pipeline.schemas import Provenance


<<<<<<< HEAD
def file_provenance(path: Path, section_path: list[str] | None = None) -> Provenance:
=======
def file_provenance(
    path: Path,
    section_path: list[str] | None = None,
    *,
    page: int | None = None,
    slide: int | None = None,
    sheet: str | None = None,
) -> Provenance:
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    """Create baseline file-level provenance for a block."""

    return Provenance(
        source_path=str(path),
<<<<<<< HEAD
        location_type="file",
=======
        location_type="slide" if slide is not None else "page" if page is not None else "sheet" if sheet else "file",
        page=page,
        slide=slide,
        sheet=sheet,
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
        section_path=list(section_path or []),
    )
