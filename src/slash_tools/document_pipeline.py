from __future__ import annotations

from pathlib import Path

from src.document_pipeline.low_level import detect_file_type, normalize_text, read_file_bytes
from src.document_pipeline.mid_level import ExtractionContext, build_doc_map, chunk_sections
from src.document_pipeline.mid_level import extract_docs as extract_docs_mid_level
from src.document_pipeline.mid_level import extract_single_doc as extract_single_doc_mid_level
from src.document_pipeline.storage import (
    load_extracted_documents_payload,
    save_chunks,
    save_document_map,
    save_extracted_documents,
    save_manifest,
    save_single_document,
)

from .context import SlashToolContext
from .errors import SlashToolError
from .path_safety import require_working_folder, resolve_workspace_path
from .serialization import documents_from_payload


def detect_file_type_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    root = require_working_folder(working_folder)
    if len(args) != 1:
        raise SlashToolError("Usage: /detect_file_type <path>")
    path = resolve_workspace_path(root, args[0])
    detected = detect_file_type(path)
    return "\n".join(
        [
            "File type detected.",
            "",
            f"- path: {_relative_to_root(path, root)}",
            f"- extension: {detected.extension}",
            f"- mime_type: {detected.mime_type}",
            f"- family: {detected.family}",
            f"- confidence: {detected.confidence}",
        ]
    )


def read_file_info_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    root = require_working_folder(working_folder)
    if len(args) != 1:
        raise SlashToolError("Usage: /read_file_info <path>")
    path = resolve_workspace_path(root, args[0])
    payload = read_file_bytes(path)
    return "\n".join(
        [
            "File info.",
            "",
            f"- path: {_relative_to_root(payload.path, root)}",
            f"- size_bytes: {payload.size_bytes}",
            f"- sha256: {payload.sha256}",
        ]
    )


def normalize_text_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    if not args:
        raise SlashToolError("Usage: /normalize_text <text>")
    return normalize_text(" ".join(args))


def extract_single_doc_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    root = require_working_folder(working_folder)
    if len(args) != 1:
        raise SlashToolError("Usage: /extract_single_doc <path>")
    context.reset_for_folder(root) if context.working_folder != root else None
    path = resolve_workspace_path(root, args[0])
    document = extract_single_doc_mid_level(path, ExtractionContext(working_folder=root))
    context.documents = [document]
    saved_document = save_single_document(root, document)
    save_extracted_documents(root, context.documents)
    manifest = save_manifest(root, context.documents)
    return "\n".join(
        [
            "Extracted 1 document.",
            "",
            _document_summary(document, root),
            "",
            "Saved:",
            f"- {_relative_to_root(saved_document, root)}",
            f"- {_relative_to_root(manifest, root)}",
        ]
    )


def extract_docs_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    root = require_working_folder(working_folder)
    if args:
        raise SlashToolError("Usage: /extract_docs")
    context.reset_for_folder(root) if context.working_folder != root else None
    documents = extract_docs_mid_level(root, ExtractionContext(working_folder=root))
    context.documents = documents
    context.doc_map = None
    context.chunks.clear()
    docs_path = save_extracted_documents(root, documents)
    manifest = save_manifest(root, documents)
    lines = [
        f"Extracted {len(documents)} document(s).",
        "",
        "Documents:",
    ]
    lines.extend([f"- {_document_summary(document, root)}" for document in documents] or ["- none"])
    lines.extend(
        [
            "",
            "Saved:",
            f"- {_relative_to_root(docs_path, root)}",
            f"- {_relative_to_root(manifest, root)}",
        ]
    )
    return "\n".join(lines)


def build_doc_map_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    root = require_working_folder(working_folder)
    if args:
        raise SlashToolError("Usage: /build_doc_map")
    _ensure_documents(root, context)
    doc_map = build_doc_map(context.documents)
    context.doc_map = doc_map
    saved_path = save_document_map(root, doc_map)
    return "\n".join(
        [
            "Built document map.",
            "",
            f"- documents: {len(doc_map.documents)}",
            f"- blocks: {len(doc_map.blocks)}",
            "",
            "Saved:",
            f"- {_relative_to_root(saved_path, root)}",
        ]
    )


def chunk_sections_command(args: list[str], working_folder: str | Path | None, context: SlashToolContext) -> str:
    root = require_working_folder(working_folder)
    max_chars = _parse_max_chars(args)
    _ensure_documents(root, context)
    chunks = chunk_sections(context.documents, max_chars=max_chars)
    context.chunks = chunks
    saved_path = save_chunks(root, chunks)
    return "\n".join(
        [
            "Built retrieval chunks.",
            "",
            f"- chunks: {len(chunks)}",
            f"- max_chars: {max_chars}",
            "",
            "Saved:",
            f"- {_relative_to_root(saved_path, root)}",
        ]
    )


def _ensure_documents(root: Path, context: SlashToolContext) -> None:
    if context.working_folder != root:
        context.reset_for_folder(root)
    if context.documents:
        return
    try:
        context.documents = documents_from_payload(load_extracted_documents_payload(root))
    except FileNotFoundError as exc:
        raise SlashToolError("Run /extract_docs first, or restore extracted_documents.json.") from exc
    except (OSError, ValueError) as exc:
        raise SlashToolError(f"Could not load extracted_documents.json: {exc}") from exc


def _parse_max_chars(args: list[str]) -> int:
    if not args:
        return 2400
    if len(args) != 2 or args[0] != "--max-chars":
        raise SlashToolError("Usage: /chunk_sections [--max-chars N]")
    try:
        value = int(args[1])
    except ValueError as exc:
        raise SlashToolError("--max-chars must be an integer.") from exc
    if value < 200:
        raise SlashToolError("--max-chars must be at least 200.")
    return value


def _document_summary(document, root: Path) -> str:
    return (
        f"{_relative_to_root(Path(document.source.path), root)}: "
        f"{len(document.blocks)} block(s), {len(document.assets)} asset(s)"
    )


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)
