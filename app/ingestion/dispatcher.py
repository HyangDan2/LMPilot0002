from __future__ import annotations

from pathlib import Path

from app.ingestion.parsers.base import DocumentParser, ParserError
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.parsers.pptx_parser import PptxParser
from app.ingestion.parsers.xlsx_parser import XlsxParser
from app.models.schemas import ParsedDocument


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


def parse_document(path: Path) -> ParsedDocument:
    """Parse one supported file into the common schema."""

    return parser_for_path(path).parse(path)

