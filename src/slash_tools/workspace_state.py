from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.document_pipeline.storage import pipeline_output_dir


@dataclass(frozen=True)
class WorkspaceState:
    working_folder: str
    extracted_documents_path: str | None = None
    extraction_manifest_path: str | None = None
    document_map_path: str | None = None
    chunks_path: str | None = None
    output_plan_path: str | None = None
    chunk_summaries_path: str | None = None
    section_summaries_path: str | None = None
    report_attempts_path: str | None = None
    generated_markdown_path: str | None = None
    document_count: int = 0
    chunk_count: int = 0
    next_actions: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            "Workspace status",
            "",
            "Attached folder:",
            self.working_folder,
            "",
            "Artifacts:",
            f"- extracted_documents.json: {_found(self.extracted_documents_path, self.document_count, 'document(s)')}",
            f"- extraction_manifest.json: {_found(self.extraction_manifest_path)}",
            f"- document_map.json: {_found(self.document_map_path)}",
            f"- chunks.json: {_found(self.chunks_path, self.chunk_count, 'chunk(s)')}",
            f"- output_plan.json: {_found(self.output_plan_path)}",
            f"- llm_chunk_summaries.json: {_found(self.chunk_summaries_path)}",
            f"- llm_section_summaries.json: {_found(self.section_summaries_path)}",
            f"- llm_report_attempts.json: {_found(self.report_attempts_path)}",
            f"- generated_report.md: {_found(self.generated_markdown_path)}",
        ]
        if self.next_actions:
            lines.extend(["", "Suggested next:"])
            lines.extend(f"- {action}" for action in self.next_actions)
        return "\n".join(lines)


def load_workspace_state(working_folder: Path) -> WorkspaceState:
    root = working_folder.expanduser().resolve()
    output_dir = pipeline_output_dir(root)
    extracted_path = output_dir / "extracted_documents.json"
    manifest_path = output_dir / "extraction_manifest.json"
    doc_map_path = output_dir / "document_map.json"
    chunks_path = output_dir / "chunks.json"
    output_plan_path = output_dir / "output_plan.json"
    chunk_summaries_path = output_dir / "llm_chunk_summaries.json"
    section_summaries_path = output_dir / "llm_section_summaries.json"
    attempts_path = output_dir / "llm_report_attempts.json"
    report_path = output_dir / "generated_report.md"
    document_count = _document_count(extracted_path)
    chunk_count = _chunk_count(chunks_path)
    next_actions = _next_actions(
        has_documents=extracted_path.exists() and document_count > 0,
        has_map=doc_map_path.exists(),
        has_chunks=chunks_path.exists(),
        has_output_plan=output_plan_path.exists(),
        has_report=report_path.exists(),
    )
    return WorkspaceState(
        working_folder=str(root),
        extracted_documents_path=_path_if_exists(extracted_path, root),
        extraction_manifest_path=_path_if_exists(manifest_path, root),
        document_map_path=_path_if_exists(doc_map_path, root),
        chunks_path=_path_if_exists(chunks_path, root),
        output_plan_path=_path_if_exists(output_plan_path, root),
        chunk_summaries_path=_path_if_exists(chunk_summaries_path, root),
        section_summaries_path=_path_if_exists(section_summaries_path, root),
        report_attempts_path=_path_if_exists(attempts_path, root),
        generated_markdown_path=_path_if_exists(report_path, root),
        document_count=document_count,
        chunk_count=chunk_count,
        next_actions=next_actions,
    )


def _path_if_exists(path: Path, root: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _document_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    documents = payload.get("documents") if isinstance(payload, dict) else None
    return len(documents) if isinstance(documents, list) else 0


def _chunk_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    chunks = payload.get("chunks") if isinstance(payload, dict) else None
    return len(chunks) if isinstance(chunks, list) else 0


def _next_actions(
    has_documents: bool,
    has_map: bool,
    has_chunks: bool,
    has_output_plan: bool,
    has_report: bool,
) -> list[str]:
    if not has_documents:
        return ["/generate_report", "/extract_docs"]
    if not has_map:
        return ["/generate_report", "/build_doc_map"]
    if not has_chunks:
        return ["/generate_report", "/chunk_sections"]
    if not has_output_plan or not has_report:
        return ["/generate_report"]
    return ["Ask a normal question about the generated report", "Re-run /extract_docs if source files changed"]


def _found(path: str | None, count: int | None = None, unit: str = "") -> str:
    if path is None:
        return "missing"
    if count is None:
        return f"found ({path})"
    return f"found, {count} {unit} ({path})"
