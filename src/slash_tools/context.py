from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument


@dataclass
class SlashToolContext:
    """Runtime state shared by local slash tools in one GUI window."""

    working_folder: Path | None = None
    documents: list[ExtractedDocument] = field(default_factory=list)
    doc_map: DocumentMap | None = None
    chunks: list[EvidenceChunk] = field(default_factory=list)
    saved_files: list[str] = field(default_factory=list)
    last_tool_name: str = ""
    last_tool_summary: str = ""

    def reset_for_folder(self, working_folder: Path | None) -> None:
        self.working_folder = working_folder
        self.documents.clear()
        self.doc_map = None
        self.chunks.clear()
        self.saved_files.clear()
        self.last_tool_name = ""
        self.last_tool_summary = ""
