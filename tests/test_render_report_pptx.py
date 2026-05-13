import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from src.document_pipeline.high_level import build_presentation_plan_from_markdown, render_report_pptx_pipeline
from src.document_pipeline.schemas import AssetRef, DocumentMetadata, ExtractedBlock, ExtractedDocument, Provenance, SourceInfo
from src.document_pipeline.storage import pipeline_output_dir, save_extracted_documents
from src.slash_tools import SlashToolContext, run_slash_command


class RenderReportPptxTests(unittest.TestCase):
    def test_build_presentation_plan_from_markdown_selects_matching_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            document = _sample_document(root)
            markdown = (
                "# Engineering Report\n\n"
                "## Summary\n"
                "System diagram confirms the architecture flow.\n"
                "## Open Issues and Next Actions\n"
                "Validate the architecture against test data.\n"
            )

            plan = build_presentation_plan_from_markdown(markdown, [document])

            self.assertEqual(plan.title, "Engineering Report")
            self.assertEqual(plan.slides[0].slide_title, "Summary")
            self.assertTrue(plan.slides[0].image_path.endswith(".png"))
            self.assertEqual(plan.slides[0].image_refs, ["asset_arch"])

    def test_render_report_pptx_pipeline_saves_plan_and_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = pipeline_output_dir(root)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "generated_report.md").write_text(
                "# Engineering Report\n\n## Summary\nSystem diagram confirms the architecture flow.\n",
                encoding="utf-8",
            )
            save_extracted_documents(root, [_sample_document(root)])

            with patch.dict("sys.modules", _fake_pptx_modules()):
                result = render_report_pptx_pipeline(root)

            self.assertTrue(result.plan_path.exists())
            self.assertTrue(result.output_pptx.exists())
            payload = json.loads(result.plan_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "Engineering Report")
            self.assertEqual(result.image_slide_count, 1)

    def test_render_report_pptx_slash_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = pipeline_output_dir(root)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "generated_report.md").write_text(
                "# Engineering Report\n\n## Summary\nSystem diagram confirms the architecture flow.\n",
                encoding="utf-8",
            )
            save_extracted_documents(root, [_sample_document(root)])

            with patch.dict("sys.modules", _fake_pptx_modules()):
                result = run_slash_command("/render_report_pptx", root, SlashToolContext())

        assert result is not None
        self.assertIn("Rendered report PPTX", result.text)
        self.assertIn("generated_report.pptx", result.text)
        self.assertIn("presentation_plan.json", result.text)


def _sample_document(root: Path) -> ExtractedDocument:
    asset_path = root / "llm_result" / "document_pipeline" / "assets" / "doc_report" / "asset_arch.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"png")
    provenance = Provenance(source_path=str(root / "report.pptx"), location_type="slide", slide=1)
    return ExtractedDocument(
        schema_version="0.1",
        document_id="doc_report",
        source=SourceInfo(
            path=str(root / "report.pptx"),
            filename="report.pptx",
            extension=".pptx",
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            size_bytes=6,
            sha256="abc",
        ),
        metadata=DocumentMetadata(title="Report"),
        blocks=[
            ExtractedBlock(
                block_id="blk_asset_001",
                document_id="doc_report",
                type="image",
                role="image_asset",
                order=0,
                text="Embedded image artifact extracted from the source document. Caption or shape name: System diagram.",
                normalized_text="Embedded image artifact extracted from the source document. Caption or shape name: System diagram.",
                provenance=provenance,
                asset_ids=["asset_arch"],
            )
        ],
        assets=[
            AssetRef(
                asset_id="asset_arch",
                document_id="doc_report",
                type="image",
                source_path=str(root / "report.pptx"),
                stored_path=str(asset_path),
                mime_type="image/png",
                sha256="def",
                width=320,
                height=240,
                caption="System diagram",
                provenance=provenance,
                metadata={"shape_name": "System diagram"},
            )
        ],
    )


def _fake_pptx_modules() -> dict[str, ModuleType]:
    pptx = ModuleType("pptx")
    pptx.Presentation = FakePresentation
    util = ModuleType("pptx.util")
    util.Inches = lambda value: value
    util.Pt = lambda value: value
    return {"pptx": pptx, "pptx.util": util}


class FakePresentation:
    def __init__(self) -> None:
        self.slide_layouts = [object(), object(), object(), object(), object(), object()]
        self.slides = FakeSlides()

    def save(self, path: str) -> None:
        Path(path).write_bytes(b"pptx")


class FakeSlides(list):
    def add_slide(self, layout) -> "FakeSlide":
        slide = FakeSlide()
        self.append(slide)
        return slide


class FakeSlide:
    def __init__(self) -> None:
        self.shapes = FakeShapes()
        self.placeholders = [SimpleNamespace(text=""), SimpleNamespace(text="")]


class FakeShapes:
    def __init__(self) -> None:
        self.title = SimpleNamespace(text="")
        self.pictures: list[str] = []

    def add_textbox(self, left, top, width, height):
        return FakeTextBox()

    def add_picture(self, path, left, top, width=None, height=None):
        self.pictures.append(path)
        return SimpleNamespace(path=path)


class FakeTextBox:
    def __init__(self) -> None:
        self.text_frame = FakeTextFrame()


class FakeTextFrame:
    def __init__(self) -> None:
        self.paragraphs = [FakeParagraph()]

    def clear(self) -> None:
        self.paragraphs = [FakeParagraph()]

    def add_paragraph(self) -> "FakeParagraph":
        paragraph = FakeParagraph()
        self.paragraphs.append(paragraph)
        return paragraph


class FakeParagraph:
    def __init__(self) -> None:
        self.text = ""
        self.font = SimpleNamespace(size=None)
        self.level = 0


if __name__ == "__main__":
    unittest.main()
