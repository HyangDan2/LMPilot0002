from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.document_pipeline.schemas import ExtractedDocument
from src.document_pipeline.storage import (
    load_extracted_documents,
    pipeline_output_dir,
)
from src.models.schemas import PresentationPlan, SlidePlan
from src.renderer.pptx_renderer import PptxRenderer
from src.utils.io import save_json


@dataclass(frozen=True)
class RenderReportPptxResult:
    markdown_path: Path
    plan_path: Path
    output_pptx: Path
    slide_count: int
    image_slide_count: int
    saved_files: list[Path] = field(default_factory=list)


def render_report_pptx_pipeline(
    working_folder: Path,
    markdown_path: Path | None = None,
    output_filename: str | None = None,
) -> RenderReportPptxResult:
    root = working_folder.expanduser().resolve()
    output_dir = pipeline_output_dir(root)
    markdown_file = (markdown_path or (output_dir / "generated_report.md")).expanduser().resolve()
    if not markdown_file.is_file():
        raise FileNotFoundError(
            f"Generated markdown report not found: {markdown_file}. Run /generate_report or /generate_markdown first."
        )

    documents = load_extracted_documents(root)
    markdown = markdown_file.read_text(encoding="utf-8")
    plan = build_presentation_plan_from_markdown(markdown, documents)
    plan_path = output_dir / "presentation_plan.json"
    save_json(plan_path, plan.to_dict())
    pptx_name = output_filename or "generated_report.pptx"
    output_pptx = PptxRenderer().render(plan, output_dir, pptx_name)
    image_slide_count = sum(1 for slide in plan.slides if slide.image_path)
    return RenderReportPptxResult(
        markdown_path=markdown_file,
        plan_path=plan_path,
        output_pptx=output_pptx,
        slide_count=len(plan.slides) + 1,
        image_slide_count=image_slide_count,
        saved_files=[plan_path, output_pptx],
    )


def build_presentation_plan_from_markdown(
    markdown: str,
    documents: list[ExtractedDocument],
    target_audience: str = "Engineering stakeholders",
) -> PresentationPlan:
    title, sections = _parse_markdown_sections(markdown)
    if not sections:
        sections = [("Summary", markdown.strip())]

    image_candidates = _build_image_candidates(documents)
    used_asset_ids: set[str] = set()
    slides: list[SlidePlan] = []
    for section_title, section_body in sections:
        bullets = _section_bullets(section_title, section_body)
        if not bullets:
            bullets = ["No summary text was available for this section."]
        chunks = _chunk_bullets(bullets, 5)
        for index, chunk in enumerate(chunks, start=1):
            slide_title = section_title if len(chunks) == 1 else f"{section_title} ({index})"
            purpose = chunk[0]
            image = _select_image_for_slide(slide_title, chunk, image_candidates, used_asset_ids)
            if image is not None:
                used_asset_ids.add(image["asset_id"])
            slides.append(
                SlidePlan(
                    slide_title=slide_title,
                    purpose=purpose,
                    source_refs=_collect_source_refs(section_body),
                    image_refs=[image["asset_id"]] if image is not None else [],
                    bullet_points=chunk,
                    image_path=image["image_path"] if image is not None else "",
                    image_caption=image["caption"] if image is not None else "",
                )
            )
    return PresentationPlan(output_type="pptx", title=title, target_audience=target_audience, slides=slides)


def _parse_markdown_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    lines = markdown.splitlines()
    title = "Generated Report"
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and title == "Generated Report":
            title = stripped[2:].strip() or title
            continue
        if stripped.startswith("## "):
            if current_title is not None:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = stripped[3:].strip() or "Section"
            current_lines = []
            continue
        if current_title is not None:
            current_lines.append(line)
    if current_title is not None:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return title, sections


def _section_bullets(section_title: str, section_body: str) -> list[str]:
    bullets: list[str] = []
    table_rows: list[str] = []
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            bullets.append(line[4:].strip())
            continue
        if line.startswith(("- ", "* ")):
            bullets.append(line[2:].strip())
            continue
        if re.match(r"^\d+\.\s+", line):
            bullets.append(re.sub(r"^\d+\.\s+", "", line))
            continue
        if line.startswith("|") and line.endswith("|"):
            if "---" in line:
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if any(cells):
                table_rows.append(": ".join(cell for cell in cells if cell))
            continue
        bullets.append(line)
    if table_rows:
        bullets.extend(table_rows[:4] if section_title.lower().startswith("source") else table_rows)
    deduped: list[str] = []
    seen: set[str] = set()
    for bullet in bullets:
        normalized = " ".join(bullet.split())
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped[:8]


def _chunk_bullets(bullets: list[str], max_per_slide: int) -> list[list[str]]:
    return [bullets[index : index + max_per_slide] for index in range(0, len(bullets), max_per_slide)]


def _collect_source_refs(section_body: str) -> list[str]:
    refs = re.findall(r"\b([\w.-]+\.(?:pptx|pdf|docx|xlsx))\b", section_body, flags=re.IGNORECASE)
    unique: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        normalized = ref.strip()
        if normalized and normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return unique[:4]


def _build_image_candidates(documents: list[ExtractedDocument]) -> list[dict[str, str]]:
    blocks_by_asset_id: dict[str, list[str]] = {}
    for document in documents:
        for block in document.blocks:
            if block.type != "image" or not block.asset_ids:
                continue
            for asset_id in block.asset_ids:
                blocks_by_asset_id.setdefault(asset_id, []).append(block.text)

    candidates: list[dict[str, str]] = []
    for document in documents:
        for asset in document.assets:
            if asset.type != "image" or not asset.stored_path:
                continue
            if not Path(asset.stored_path).is_file():
                continue
            text_parts = [document.source.filename, asset.caption]
            text_parts.extend(blocks_by_asset_id.get(asset.asset_id, []))
            text_parts.extend(str(value) for value in asset.metadata.values() if isinstance(value, str))
            candidates.append(
                {
                    "asset_id": asset.asset_id,
                    "image_path": asset.stored_path,
                    "caption": asset.caption or Path(asset.stored_path).name,
                    "match_text": " ".join(part for part in text_parts if part).lower(),
                }
            )
    return candidates


def _select_image_for_slide(
    slide_title: str,
    bullet_points: list[str],
    candidates: list[dict[str, str]],
    used_asset_ids: set[str],
) -> dict[str, str] | None:
    query_terms = _query_terms(" ".join([slide_title, *bullet_points]))
    best_candidate: dict[str, str] | None = None
    best_score = 0
    for candidate in candidates:
        if candidate["asset_id"] in used_asset_ids:
            continue
        score = sum(2 if term in candidate["match_text"] else 0 for term in query_terms)
        if candidate["caption"] and query_terms:
            score += sum(1 for term in query_terms if term in candidate["caption"].lower())
        if score > best_score:
            best_score = score
            best_candidate = candidate
    return best_candidate if best_score > 0 else None


def _query_terms(text: str) -> set[str]:
    terms = set(re.findall(r"[A-Za-z0-9가-힣_]{3,}", text.lower()))
    stopwords = {
        "summary",
        "source",
        "sources",
        "documents",
        "open",
        "issues",
        "next",
        "actions",
        "recommendations",
    }
    return {term for term in terms if term not in stopwords}
