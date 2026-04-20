from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.document_pipeline.mid_level import ExtractionContext, build_doc_map, chunk_sections, extract_docs
from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument, OutputPlan
from src.document_pipeline.storage import (
    save_chunks,
    save_document_map,
    save_extracted_documents,
    save_generated_markdown,
    save_manifest,
    save_output_plan,
)

from .generate_report import generate_report_from_plan
from .write_output_plan import DEFAULT_REPORT_GOAL, write_output_plan


@dataclass(frozen=True)
class GenerateReportResult:
    documents: list[ExtractedDocument]
    doc_map: DocumentMap
    chunks: list[EvidenceChunk]
    output_plan: OutputPlan
    markdown: str
    saved_files: list[Path] = field(default_factory=list)


def generate_report_pipeline(
    working_folder: Path,
    goal: str = DEFAULT_REPORT_GOAL,
    max_chunk_chars: int = 2400,
) -> GenerateReportResult:
    """Run the full local report pipeline and save every intermediate artifact."""

    root = working_folder.expanduser().resolve()
    documents = extract_docs(root, ExtractionContext(working_folder=root))
    doc_map = build_doc_map(documents)
    chunks = chunk_sections(documents, max_chars=max_chunk_chars)
    output_plan = write_output_plan(documents, doc_map, chunks, goal=goal)
    markdown = generate_report_from_plan(output_plan, documents, doc_map, chunks)
    saved_files = [
        save_extracted_documents(root, documents),
        save_manifest(root, documents),
        save_document_map(root, doc_map),
        save_chunks(root, chunks),
        save_output_plan(root, output_plan),
        save_generated_markdown(root, markdown),
    ]
    return GenerateReportResult(
        documents=documents,
        doc_map=doc_map,
        chunks=chunks,
        output_plan=output_plan,
        markdown=markdown,
        saved_files=saved_files,
    )
