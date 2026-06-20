from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_DIR = PROJECT_ROOT / "prompts"
VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render_prompt(
    tool_name: str,
    variables: dict[str, object],
    fallback: str,
    prompt_dir: Path | None = None,
) -> str:
    template = load_prompt_template(tool_name, prompt_dir=prompt_dir)
    if template is None:
        template = fallback
    rendered = VARIABLE_RE.sub(lambda match: str(variables.get(match.group(1), match.group(0))), template)
    return rendered.strip()


def load_prompt_template(tool_name: str, prompt_dir: Path | None = None) -> str | None:
    root = DEFAULT_PROMPT_DIR if prompt_dir is None else prompt_dir
    path = root / f"{tool_name}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    body = strip_frontmatter(text).strip()
    return body or None


def strip_frontmatter(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return normalized
    return normalized[end + len("\n---\n") :]
