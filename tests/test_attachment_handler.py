import tempfile
import unittest
from pathlib import Path

from src.gemma_console_gui.attachment_handler import (
    AttachmentError,
    extract_text_from_file,
    format_attachment_context,
    format_user_text_with_attachments,
    validate_attachment_path,
)


class AttachmentHandlerTests(unittest.TestCase):
    def test_extract_text_from_plain_file(self) -> None:
        path = Path(tempfile.mkdtemp()) / "note.txt"
        path.write_text("hello attachment", encoding="utf-8")

        attachment = extract_text_from_file(str(path))

        self.assertEqual(attachment.filename, "note.txt")
        self.assertEqual(attachment.file_type, "txt")
        self.assertEqual(attachment.extracted_text, "hello attachment")

    def test_rejects_unsupported_file_type(self) -> None:
        path = Path(tempfile.mkdtemp()) / "archive.bin"
        path.write_bytes(b"data")

        with self.assertRaises(AttachmentError):
            extract_text_from_file(str(path))

    def test_validate_attachment_path_does_not_extract_content(self) -> None:
        path = Path(tempfile.mkdtemp()) / "note.txt"
        path.write_text("hello attachment", encoding="utf-8")

        self.assertEqual(validate_attachment_path(str(path)), path.resolve())

    def test_format_user_text_with_attachments(self) -> None:
        context = format_attachment_context(
            [
                {
                    "filename": "note.txt",
                    "file_type": "txt",
                    "extracted_text": "attachment text",
                }
            ]
        )

        prompt = format_user_text_with_attachments("summarize", context)

        self.assertIn("File name: note.txt", prompt)
        self.assertIn("attachment text", prompt)
        self.assertTrue(prompt.endswith("User message:\nsummarize"))


if __name__ == "__main__":
    unittest.main()
