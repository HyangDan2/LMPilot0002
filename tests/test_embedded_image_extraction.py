import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from src.document_pipeline.mid_level import ExtractionContext, extract_single_doc
from src.document_pipeline.storage import pipeline_output_dir
from src.ingestion.parsers.pdf_parser import PdfParser


class EmbeddedImageExtractionTests(unittest.TestCase):
    def test_extract_single_doc_pptx_writes_embedded_images_and_image_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "deck.pptx"
            _write_minimal_pptx(source)

            with patch.dict("sys.modules", _fake_pptx_modules()):
                document = extract_single_doc(source, ExtractionContext(working_folder=root))

            self.assertEqual(len(document.assets), 1)
            self.assertEqual(document.assets[0].type, "image")
            self.assertTrue(Path(document.assets[0].stored_path).exists())
            self.assertEqual(document.assets[0].provenance.slide, 1)
            image_blocks = [block for block in document.blocks if block.type == "image"]
            self.assertEqual(len(image_blocks), 1)
            self.assertIn("Embedded image artifact", image_blocks[0].text)
            self.assertEqual(image_blocks[0].asset_ids, [document.assets[0].asset_id])

    def test_extract_single_doc_docx_writes_embedded_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "spec.docx"
            _write_minimal_docx(source)

            with patch.dict("sys.modules", _fake_docx_modules()):
                document = extract_single_doc(source, ExtractionContext(working_folder=root))

            self.assertEqual(len(document.assets), 1)
            self.assertTrue(Path(document.assets[0].stored_path).exists())
            self.assertEqual(document.assets[0].mime_type, "image/png")
            image_blocks = [block for block in document.blocks if block.type == "image"]
            self.assertEqual(len(image_blocks), 1)

    def test_pdf_parser_extracts_page_images_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "report.pdf"
            source.write_bytes(b"%PDF-1.4")
            asset_dir = pipeline_output_dir(root) / "assets"

            with patch.dict("sys.modules", _fake_pypdf_modules()):
                document = PdfParser().parse(source, asset_output_dir=asset_dir)

            self.assertEqual(len(document.assets), 1)
            self.assertTrue(Path(document.assets[0].path).exists())
            self.assertEqual(document.assets[0].page_or_slide, 1)
            self.assertEqual(document.sections[0].assets[0].asset_id, document.assets[0].asset_id)

    def test_generate_report_pipeline_saves_asset_paths_in_extracted_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "deck.pptx"
            _write_minimal_pptx(source)

            with patch.dict("sys.modules", _fake_pptx_modules()):
                from src.document_pipeline.high_level import generate_report_pipeline

                generate_report_pipeline(root, goal="Summarize slide assets")

            extracted_path = pipeline_output_dir(root) / "extracted_documents.json"
            payload = json.loads(extracted_path.read_text(encoding="utf-8"))
            assets = payload["documents"][0]["assets"]
            self.assertEqual(len(assets), 1)
            self.assertTrue(Path(assets[0]["stored_path"]).exists())


def _write_minimal_pptx(path: Path) -> None:
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:pic>
        <p:nvPicPr>
          <p:cNvPr id="4" name="Diagram" descr="System diagram"/>
        </p:nvPicPr>
        <p:blipFill>
          <a:blip r:embed="rId1"/>
        </p:blipFill>
        <p:spPr>
          <a:xfrm><a:ext cx="640" cy="480"/></a:xfrm>
        </p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", slide_xml)
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", rels_xml)
        archive.writestr("ppt/media/image1.png", b"png-data")


def _write_minimal_docx(path: Path) -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline>
            <wp:extent cx="320" cy="240"/>
            <wp:docPr id="1" name="Architecture" descr="System architecture"/>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId5"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>
"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", rels_xml)
        archive.writestr("word/media/image1.png", b"png-data")


def _fake_pptx_modules() -> dict[str, ModuleType]:
    pptx = ModuleType("pptx")
    pptx.Presentation = FakePresentation
    enum_module = ModuleType("pptx.enum")
    shapes_module = ModuleType("pptx.enum.shapes")
    shapes_module.MSO_SHAPE_TYPE = SimpleNamespace(PICTURE="picture")
    return {
        "pptx": pptx,
        "pptx.enum": enum_module,
        "pptx.enum.shapes": shapes_module,
    }


def _fake_docx_modules() -> dict[str, ModuleType]:
    docx = ModuleType("docx")
    docx.Document = FakeDocument
    return {"docx": docx}


def _fake_pypdf_modules() -> dict[str, ModuleType]:
    pypdf = ModuleType("pypdf")
    pypdf.PdfReader = FakePdfReader
    return {"pypdf": pypdf}


class FakePresentation:
    def __init__(self, path: str) -> None:
        self.slides = [FakeSlide()]


class FakeSlide:
    def __init__(self) -> None:
        self.shapes = FakeShapes(
            [
                FakeTextShape("System Overview"),
                FakePictureShape("Diagram", width=640, height=480),
            ]
        )


class FakeShapes(list):
    @property
    def title(self):
        return self[0]


class FakeTextShape:
    shape_type = "text"
    has_text_frame = True

    def __init__(self, text: str) -> None:
        self.text_frame = SimpleNamespace(paragraphs=[SimpleNamespace(text=text)])


class FakePictureShape:
    shape_type = "picture"
    has_text_frame = False

    def __init__(self, name: str, width: int, height: int) -> None:
        self.name = name
        self.width = width
        self.height = height


class FakeDocument:
    def __init__(self, path: str) -> None:
        self.paragraphs = [
            SimpleNamespace(text="Architecture Review", style=SimpleNamespace(name="Heading 1")),
            SimpleNamespace(text="Image is embedded below.", style=SimpleNamespace(name="Normal")),
        ]


class FakePdfImage:
    def __init__(self) -> None:
        self.data = b"image-bytes"
        self.name = "page1-image.png"
        self.image = SimpleNamespace(width=100, height=50)


class FakePdfPage:
    def __init__(self) -> None:
        self.images = [FakePdfImage()]

    def extract_text(self) -> str:
        return "PDF page text"


class FakePdfReader:
    def __init__(self, path: str) -> None:
        self.pages = [FakePdfPage()]


if __name__ == "__main__":
    unittest.main()
