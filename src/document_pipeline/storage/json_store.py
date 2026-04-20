from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.document_pipeline.schemas import DocumentMap, EvidenceChunk, ExtractedDocument


def pipeline_output_dir(working_folder: Path) -> Path:
    """Return the automatic artifact folder for document pipeline outputs."""

    return working_folder.expanduser().resolve() / "llm_result" / "document_pipeline"


def save_extracted_documents(working_folder: Path, documents: list[ExtractedDocument]) -> Path:
    path = pipeline_output_dir(working_folder) / "extracted_documents.json"
    _write_json(path, {"documents": [document.to_dict() for document in documents]})
    return path


def save_single_document(working_folder: Path, document: ExtractedDocument) -> Path:
    path = pipeline_output_dir(working_folder) / "documents" / f"{document.document_id}.json"
    _write_json(path, document.to_dict())
    return path


def save_document_map(working_folder: Path, doc_map: DocumentMap) -> Path:
    path = pipeline_output_dir(working_folder) / "document_map.json"
    _write_json(path, doc_map.to_dict())
    return path


def save_chunks(working_folder: Path, chunks: list[EvidenceChunk]) -> Path:
    path = pipeline_output_dir(working_folder) / "chunks.json"
    _write_json(path, {"chunks": [chunk.to_dict() for chunk in chunks]})
    return path


def save_generated_markdown(working_folder: Path, markdown: str) -> Path:
    path = pipeline_output_dir(working_folder) / "generated_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def save_manifest(working_folder: Path, documents: list[ExtractedDocument]) -> Path:
    path = pipeline_output_dir(working_folder) / "extraction_manifest.json"
    payload = {
        "document_count": len(documents),
        "documents": [
            {
                "document_id": document.document_id,
                "path": document.source.path,
                "filename": document.source.filename,
                "sha256": document.source.sha256,
                "block_count": len(document.blocks),
                "asset_count": len(document.assets),
                "warnings": list(document.warnings),
            }
            for document in documents
        ],
    }
    _write_json(path, payload)
    return path


def load_extracted_documents_payload(working_folder: Path) -> dict[str, Any]:
    path = pipeline_output_dir(working_folder) / "extracted_documents.json"
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("extracted_documents.json must contain a JSON object.")
    return payload


def load_document_map_payload(working_folder: Path) -> dict[str, Any]:
    path = pipeline_output_dir(working_folder) / "document_map.json"
    return _read_json_object(path, "document_map.json")


def load_chunks_payload(working_folder: Path) -> dict[str, Any]:
    path = pipeline_output_dir(working_folder) / "chunks.json"
    return _read_json_object(path, "chunks.json")


def load_manifest_payload(working_folder: Path) -> dict[str, Any]:
    path = pipeline_output_dir(working_folder) / "extraction_manifest.json"
    return _read_json_object(path, "extraction_manifest.json")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return payload
