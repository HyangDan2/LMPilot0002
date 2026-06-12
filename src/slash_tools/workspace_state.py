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
<<<<<<< HEAD
=======
    assets_path: str | None = None
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    document_map_path: str | None = None
    output_plan_path: str | None = None
    selected_evidence_path: str | None = None
    evidence_groups_path: str | None = None
    selected_evidence_groups_path: str | None = None
    group_summaries_path: str | None = None
    recursive_summary_levels_path: str | None = None
    final_prompt_preview_path: str | None = None
    detail_summaries_json_path: str | None = None
    detail_summaries_markdown_path: str | None = None
    report_attempts_path: str | None = None
    generated_markdown_path: str | None = None
<<<<<<< HEAD
    file_summaries_path: str | None = None
    document_count: int = 0
=======
    presentation_plan_path: str | None = None
    generated_pptx_path: str | None = None
    file_summaries_path: str | None = None
    document_count: int = 0
    asset_document_count: int = 0
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    file_summary_count: int = 0
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
<<<<<<< HEAD
=======
            f"- assets/: {_found(self.assets_path, self.asset_document_count, 'document folder(s)')}",
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
            f"- document_map.json: {_found(self.document_map_path)}",
            f"- output_plan.json: {_found(self.output_plan_path)}",
            f"- selected_evidence.json: {_found(self.selected_evidence_path)}",
            f"- evidence_groups.json: {_found(self.evidence_groups_path)}",
            f"- selected_evidence_groups.json: {_found(self.selected_evidence_groups_path)}",
            f"- group_summaries.json: {_found(self.group_summaries_path)}",
            f"- recursive_summary_levels.json: {_found(self.recursive_summary_levels_path)}",
            f"- final_prompt_preview.txt: {_found(self.final_prompt_preview_path)}",
            f"- detail_summaries.json: {_found(self.detail_summaries_json_path)}",
            f"- detail_summaries.md: {_found(self.detail_summaries_markdown_path)}",
            f"- llm_report_attempts.json: {_found(self.report_attempts_path)}",
            f"- generated_report.md: {_found(self.generated_markdown_path)}",
<<<<<<< HEAD
=======
            f"- presentation_plan.json: {_found(self.presentation_plan_path)}",
            f"- generated_report.pptx: {_found(self.generated_pptx_path)}",
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
            f"- file_summaries/: {_found(self.file_summaries_path, self.file_summary_count, 'summary folder(s)')}",
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
<<<<<<< HEAD
=======
    assets_path = output_dir / "assets"
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    doc_map_path = output_dir / "document_map.json"
    output_plan_path = output_dir / "output_plan.json"
    selected_evidence_path = output_dir / "selected_evidence.json"
    evidence_groups_path = output_dir / "evidence_groups.json"
    selected_evidence_groups_path = output_dir / "selected_evidence_groups.json"
    group_summaries_path = output_dir / "group_summaries.json"
    recursive_summary_levels_path = output_dir / "recursive_summary_levels.json"
    final_prompt_preview_path = output_dir / "final_prompt_preview.txt"
    detail_summaries_json_path = output_dir / "detail_summaries.json"
    detail_summaries_markdown_path = output_dir / "detail_summaries.md"
    attempts_path = output_dir / "llm_report_attempts.json"
    report_path = output_dir / "generated_report.md"
<<<<<<< HEAD
    file_summaries_path = output_dir / "file_summaries"
    document_count = _document_count(extracted_path)
=======
    presentation_plan_path = output_dir / "presentation_plan.json"
    generated_pptx_path = output_dir / "generated_report.pptx"
    file_summaries_path = output_dir / "file_summaries"
    document_count = _document_count(extracted_path)
    asset_document_count = _child_dir_count(assets_path)
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    file_summary_count = _file_summary_count(file_summaries_path)
    next_actions = _next_actions(
        has_documents=extracted_path.exists() and document_count > 0,
        has_map=doc_map_path.exists(),
        has_output_plan=output_plan_path.exists(),
        has_report=report_path.exists(),
    )
    return WorkspaceState(
        working_folder=str(root),
        extracted_documents_path=_path_if_exists(extracted_path, root),
        extraction_manifest_path=_path_if_exists(manifest_path, root),
<<<<<<< HEAD
=======
        assets_path=_path_if_exists(assets_path, root),
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
        document_map_path=_path_if_exists(doc_map_path, root),
        output_plan_path=_path_if_exists(output_plan_path, root),
        selected_evidence_path=_path_if_exists(selected_evidence_path, root),
        evidence_groups_path=_path_if_exists(evidence_groups_path, root),
        selected_evidence_groups_path=_path_if_exists(selected_evidence_groups_path, root),
        group_summaries_path=_path_if_exists(group_summaries_path, root),
        recursive_summary_levels_path=_path_if_exists(recursive_summary_levels_path, root),
        final_prompt_preview_path=_path_if_exists(final_prompt_preview_path, root),
        detail_summaries_json_path=_path_if_exists(detail_summaries_json_path, root),
        detail_summaries_markdown_path=_path_if_exists(detail_summaries_markdown_path, root),
        report_attempts_path=_path_if_exists(attempts_path, root),
        generated_markdown_path=_path_if_exists(report_path, root),
<<<<<<< HEAD
        file_summaries_path=_path_if_exists(file_summaries_path, root),
        document_count=document_count,
=======
        presentation_plan_path=_path_if_exists(presentation_plan_path, root),
        generated_pptx_path=_path_if_exists(generated_pptx_path, root),
        file_summaries_path=_path_if_exists(file_summaries_path, root),
        document_count=document_count,
        asset_document_count=asset_document_count,
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
        file_summary_count=file_summary_count,
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


def _file_summary_count(path: Path) -> int:
<<<<<<< HEAD
=======
    return _child_dir_count(path)


def _child_dir_count(path: Path) -> int:
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3
    if not path.is_dir():
        return 0
    return sum(1 for child in path.iterdir() if child.is_dir())


def _next_actions(
    has_documents: bool,
    has_map: bool,
    has_output_plan: bool,
    has_report: bool,
) -> list[str]:
    if not has_documents:
        return ["/generate_report summarize all output in this folder", "/extract_docs"]
    if not has_map:
        return ["/generate_report summarize all output in this folder", "/build_doc_map"]
    if not has_output_plan or not has_report:
        return ["/generate_report summarize all output in this folder"]
<<<<<<< HEAD
    return ["Ask a normal question about the generated report", "Re-run /extract_docs if source files changed"]
=======
    return ["/render_report_pptx", "Ask a normal question about the generated report"]
>>>>>>> 4b1f4179239ca3b0466426fe629135dfeba590a3


def _found(path: str | None, count: int | None = None, unit: str = "") -> str:
    if path is None:
        return "missing"
    if count is None:
        return f"found ({path})"
    return f"found, {count} {unit} ({path})"
