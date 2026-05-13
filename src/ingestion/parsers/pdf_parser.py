from __future__ import annotations

from pathlib import Path

from src.ingestion.parsers.base import DocumentParser, ParserError
from src.ingestion.parsers.asset_utils import guess_mime_type, write_asset_file
from src.models.schemas import Asset, ParsedDocument, Section


class PdfParser(DocumentParser):
    """PDF parser using pypdf text extraction plus embedded images when available."""

    file_type = "pdf"

    def parse(self, path: Path, asset_output_dir: Path | None = None) -> ParsedDocument:
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except Exception as exc:
            raise ParserError("PDF parsing requires pypdf.") from exc

        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise ParserError(f"Failed to open PDF {path}: {exc}") from exc

        doc_id = self.doc_id(path)
        sections: list[Section] = []
        assets: list[Asset] = []
        pages_text: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages_text.append(text)
            page_assets = _extract_page_images(page, path, doc_id, index, asset_output_dir)
            assets.extend(page_assets)
            sections.append(
                Section(
                    section_id=f"{doc_id}-page-{index}",
                    title=f"Page {index}",
                    level=1,
                    text=text,
                    page_or_slide=index,
                    assets=page_assets,
                    metadata={"parser": "pdf"},
                )
            )

        return ParsedDocument(
            doc_id=doc_id,
            file_path=str(path.resolve()),
            file_type=self.file_type,
            title=self.title_from_path(path),
            text="\n\n".join(pages_text).strip(),
            sections=sections,
            assets=assets,
            metadata={"page_count": len(reader.pages)},
        )


def _extract_page_images(page, path: Path, doc_id: str, page_number: int, asset_output_dir: Path | None) -> list[Asset]:
    page_images = getattr(page, "images", None)
    if page_images is None:
        return []
    try:
        iterator = list(page_images)
    except TypeError:
        return []

    assets: list[Asset] = []
    for image_index, image in enumerate(iterator, start=1):
        data = getattr(image, "data", None)
        if not isinstance(data, (bytes, bytearray)):
            continue
        name = str(getattr(image, "name", "") or f"page-{page_number}-image-{image_index}.bin")
        asset_id = f"{doc_id}-page-{page_number}-image-{image_index:04d}"
        stored_path, sha256 = write_asset_file(asset_output_dir, doc_id, asset_id, name, bytes(data))
        pil_image = getattr(image, "image", None)
        assets.append(
            Asset(
                asset_id=asset_id,
                kind="image",
                source_file=str(path.resolve()),
                page_or_slide=page_number,
                path=stored_path,
                caption=name,
                mime_type=guess_mime_type(name),
                sha256=sha256,
                width=getattr(pil_image, "width", None),
                height=getattr(pil_image, "height", None),
                metadata={"image_name": name},
            )
        )
    return assets
