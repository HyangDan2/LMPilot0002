from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.ingestion.dispatcher import parse_document
from src.models.schemas import ParsedDocument

from src.document_pipeline.low_level.normalize import normalize_text
from src.document_pipeline.low_level.provenance import file_provenance
from src.document_pipeline.schemas import AssetRef, DocumentMetadata, ExtractedBlock


class DocumentAdapter(Protocol):
    """Format adapter boundary for extracting canonical blocks and assets."""

    supported_extensions: set[str]

    def extract_metadata(self, path: Path, parsed: ParsedDocument | None = None) -> DocumentMetadata:
        ...

    def extract_blocks(self, path: Path, document_id: str, parsed: ParsedDocument) -> list[ExtractedBlock]:
        ...

    def extract_assets(self, path: Path, document_id: str, parsed: ParsedDocument) -> list[AssetRef]:
        ...


class LegacyParserAdapter:
    """Bridge existing src.ingestion parsers into the new intermediate schema."""

    supported_extensions = {".pptx", ".docx", ".xlsx", ".pdf"}

    def parse(self, path: Path, asset_output_dir: Path | None = None) -> ParsedDocument:
        return parse_document(path, asset_output_dir=asset_output_dir)

    def extract_metadata(self, path: Path, parsed: ParsedDocument | None = None) -> DocumentMetadata:
        parsed = parsed or self.parse(path)
        metadata = dict(parsed.metadata)
        return DocumentMetadata(
            title=parsed.title,
            page_count=_optional_int(metadata.get("page_count")),
            slide_count=_optional_int(metadata.get("slide_count")),
            sheet_count=_optional_int(metadata.get("sheet_count")),
            extra=metadata,
        )

    def extract_blocks(self, path: Path, document_id: str, parsed: ParsedDocument) -> list[ExtractedBlock]:
        blocks: list[ExtractedBlock] = []
        order = 0
        if parsed.text:
            blocks.append(
                ExtractedBlock(
                    block_id=f"{document_id}_text_0001",
                    document_id=document_id,
                    type="text",
                    role="document_text",
                    order=order,
                    text=parsed.text,
                    normalized_text=normalize_text(parsed.text),
                    provenance=file_provenance(path),
                )
            )
            order += 1

        for index, section in enumerate(parsed.sections, start=1):
            section_path = [section.title] if section.title else []
            blocks.append(
                ExtractedBlock(
                    block_id=f"{document_id}_section_{index:04d}",
                    document_id=document_id,
                    type="text",
                    role="section",
                    order=order,
                    text=section.text,
                    normalized_text=normalize_text(section.text),
                    level=section.level,
                    asset_ids=[asset.asset_id for asset in section.assets],
                    provenance=file_provenance(path, section_path=section_path),
                    metadata={
                        "title": section.title,
                        "page_or_slide": section.page_or_slide,
                        **section.metadata,
                    },
                )
            )
            order += 1
        for index, asset in enumerate(parsed.assets, start=1):
            text = _asset_block_text(asset)
            if not text:
                continue
            page, slide = _page_and_slide(asset.page_or_slide, path.suffix.lower())
            blocks.append(
                ExtractedBlock(
                    block_id=f"{document_id}_asset_{index:04d}",
                    document_id=document_id,
                    type="image",
                    role="image_asset",
                    order=order,
                    text=text,
                    normalized_text=normalize_text(text),
                    asset_ids=[asset.asset_id],
                    provenance=file_provenance(path, page=page, slide=slide),
                    metadata={
                        "asset_id": asset.asset_id,
                        "caption": asset.caption,
                        "stored_path": asset.path,
                        "mime_type": asset.mime_type,
                        "width": asset.width,
                        "height": asset.height,
                        **asset.metadata,
                    },
                )
            )
            order += 1
        return blocks

    def extract_assets(self, path: Path, document_id: str, parsed: ParsedDocument) -> list[AssetRef]:
        refs: list[AssetRef] = []
        for asset in parsed.assets:
            page, slide = _page_and_slide(asset.page_or_slide, path.suffix.lower())
            refs.append(
                AssetRef(
                    asset_id=asset.asset_id,
                    document_id=document_id,
                    type=asset.kind,
                    source_path=asset.source_file,
                    stored_path=asset.path,
                    mime_type=asset.mime_type,
                    sha256=asset.sha256,
                    width=asset.width,
                    height=asset.height,
                    caption=asset.caption,
                    provenance=file_provenance(path, page=page, slide=slide),
                    metadata={
                        "page_or_slide": asset.page_or_slide,
                        **asset.metadata,
                    },
                )
            )
        return refs


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _asset_block_text(asset) -> str:
    parts = ["Embedded image artifact extracted from the source document."]
    if asset.page_or_slide is not None:
        parts.append(f"Location: {asset.page_or_slide}.")
    if asset.caption:
        parts.append(f"Caption or shape name: {asset.caption}.")
    if asset.mime_type:
        parts.append(f"MIME type: {asset.mime_type}.")
    if asset.width is not None and asset.height is not None:
        parts.append(f"Dimensions: {asset.width} x {asset.height}.")
    if asset.path:
        parts.append(f"Extracted file: {Path(asset.path).name}.")
    return " ".join(part.strip() for part in parts if part.strip())


def _page_and_slide(page_or_slide: int | str | None, suffix: str) -> tuple[int | None, int | None]:
    if not isinstance(page_or_slide, int):
        return None, None
    if suffix == ".pdf":
        return page_or_slide, None
    if suffix == ".pptx":
        return None, page_or_slide
    return None, None
