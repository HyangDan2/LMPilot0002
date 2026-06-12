from __future__ import annotations

from pathlib import Path

from src.ingestion.parsers.base import DocumentParser, ParserError
from src.ingestion.parsers.docx_parser import DocxParser
from src.ingestion.parsers.pdf_parser import PdfParser
from src.ingestion.parsers.pptx_parser import PptxParser
from src.ingestion.parsers.xlsx_parser import XlsxParser
from src.models.schemas import ParsedDocument


PARSERS: dict[str, type[DocumentParser]] = {
    ".docx": DocxParser,
    ".pdf": PdfParser,
    ".pptx": PptxParser,
    ".xlsx": XlsxParser,
}


def parser_for_path(path: Path) -> DocumentParser:
    """Return the parser implementation for a file extension."""

    parser_class = PARSERS.get(path.suffix.lower())
    if parser_class is None:
        raise ParserError(f"Unsupported file type: {path.suffix}")
    return parser_class()


<<<<<<< HEAD
def parse_document(path: Path) -> ParsedDocument:
    """Parse one supported file into the common schema."""

    return parser_for_path(path).parse(path)

=======
def parse_document(path: Path, asset_output_dir: Path | None = None) -> ParsedDocument:
    """Parse one supported file into the common schema."""

    return parser_for_path(path).parse(path, asset_output_dir=asset_output_dir)
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
