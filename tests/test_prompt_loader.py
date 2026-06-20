import tempfile
import unittest
from pathlib import Path

from src.slash_tools.prompt_loader import render_prompt, strip_frontmatter


class PromptLoaderTests(unittest.TestCase):
    def test_strips_frontmatter(self) -> None:
        text = "---\nname: demo\n---\n\nBody {{value}}"

        self.assertEqual(strip_frontmatter(text).strip(), "Body {{value}}")

    def test_renders_prompt_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = Path(temp_dir)
            (prompt_dir / "demo.md").write_text(
                "---\nname: demo\n---\n\nFile: {{name}}\nInstruction: {{instruction}}",
                encoding="utf-8",
            )

            rendered = render_prompt(
                "demo",
                {"name": "a.xlsx", "instruction": "Summarize it."},
                "fallback",
                prompt_dir=prompt_dir,
            )

        self.assertIn("File: a.xlsx", rendered)
        self.assertIn("Instruction: Summarize it.", rendered)

    def test_uses_fallback_when_prompt_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rendered = render_prompt("missing", {}, "Default prompt", prompt_dir=Path(temp_dir))

        self.assertEqual(rendered, "Default prompt")


if __name__ == "__main__":
    unittest.main()
