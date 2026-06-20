import tempfile
import unittest
from pathlib import Path

from src.slash_tools.prompt_loader import render_prompt, strip_frontmatter


class PromptLoaderTests(unittest.TestCase):
    def test_strips_frontmatter(self) -> None:
        text = "---\nname: demo\n---\n\n본문 {{value}}"

        self.assertEqual(strip_frontmatter(text).strip(), "본문 {{value}}")

    def test_renders_prompt_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = Path(temp_dir)
            (prompt_dir / "demo.md").write_text(
                "---\nname: demo\n---\n\n파일: {{name}}\n지시: {{instruction}}",
                encoding="utf-8",
            )

            rendered = render_prompt(
                "demo",
                {"name": "a.xlsx", "instruction": "요약하라"},
                "fallback",
                prompt_dir=prompt_dir,
            )

        self.assertIn("파일: a.xlsx", rendered)
        self.assertIn("지시: 요약하라", rendered)

    def test_uses_fallback_when_prompt_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rendered = render_prompt("missing", {}, "기본 프롬프트", prompt_dir=Path(temp_dir))

        self.assertEqual(rendered, "기본 프롬프트")


if __name__ == "__main__":
    unittest.main()
