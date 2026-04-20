from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument


@dataclass
class SlashToolContext:
    """Runtime state shared by local slash tools in one GUI window."""

    working_folder: Path | None = None
    documents: list[ExtractedDocument] = field(default_factory=list)
    doc_map: DocumentMap | None = None
    chunks: list[EvidenceChunk] = field(default_factory=list)
    saved_files: list[str] = field(default_factory=list)
    llm_settings: Any | None = None
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

    def copy_for_worker(self) -> "SlashToolContext":
        return SlashToolContext(
            working_folder=self.working_folder,
            documents=list(self.documents),
            doc_map=self.doc_map,
            chunks=list(self.chunks),
            saved_files=list(self.saved_files),
            llm_settings=self.llm_settings,
            last_tool_name=self.last_tool_name,
            last_tool_summary=self.last_tool_summary,
        )

    def replace_from(self, other: "SlashToolContext") -> None:
        self.working_folder = other.working_folder
        self.documents = list(other.documents)
        self.doc_map = other.doc_map
        self.chunks = list(other.chunks)
        self.saved_files = list(other.saved_files)
        self.llm_settings = other.llm_settings
        self.last_tool_name = other.last_tool_name
        self.last_tool_summary = other.last_tool_summary
