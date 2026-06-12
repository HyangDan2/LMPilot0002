from __future__ import annotations

import re
from pathlib import Path

from src.gui.llm_client import OpenAICompatibleClient

from .context import SlashToolContext
from .errors import SlashToolError
from .extract_file import SUPPORTED_EXTRACT_EXTENSIONS, extract_file_to_markdown
from .path_safety import RESULT_ROOT_NAME, output_root, require_working_folder, resolve_inside
from .results import SlashToolResult


def evaluate_file_command(
    args: list[str],
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress=None,
) -> SlashToolResult:
    if len(args) < 2:
        raise SlashToolError("Usage: /evaluate_file <standard markdown|file> <target markdown|file> [extra prompt]")

    root = require_working_folder(working_folder)
    standard_source = args[0]
    target_source = args[1]
    instruction = " ".join(args[2:]).strip() or (
        f"{Path(standard_source).name}의 기준으로 {Path(target_source).name}의 파일의 내용을 평가하라"
    )

    standard_markdown = ensure_markdown_for_input(standard_source, root, working_folder, context, progress)
    target_markdown = ensure_markdown_for_input(target_source, root, working_folder, context, progress)

    standard_text = standard_markdown.read_text(encoding="utf-8", errors="replace")
    target_text = target_markdown.read_text(encoding="utf-8", errors="replace")
    messages = build_evaluation_messages(standard_text, target_text, instruction)

    if progress is not None:
        progress("status", "Evaluating extracted markdown with LLM...")
    context.check_cancelled()
    client = _evaluation_client(context)
    answer = client.chat_completion(messages)

    out_dir = output_root(root, "evaluate_file")
    output_path = out_dir / f"{_safe_name(Path(standard_source).name)}__vs__{_safe_name(Path(target_source).name)}.md"
    output_path.write_text(
        "\n".join(
            [
                f"# Evaluation: {Path(standard_source).name} vs {Path(target_source).name}",
                "",
                f"- Standard Markdown: `{standard_markdown}`",
                f"- Target Markdown: `{target_markdown}`",
                "",
                "## Additional Prompt",
                "",
                instruction,
                "",
                "## LLM Evaluation",
                "",
                answer.strip(),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return SlashToolResult(
        text=f"Evaluation saved:\n{output_path}\n\n{answer.strip()}",
        tool_name="/evaluate_file",
    )


def ensure_markdown_for_input(
    raw_path: str,
    root: Path,
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress=None,
) -> Path:
    source = resolve_inside(root, raw_path)
    if not source.exists():
        raise SlashToolError(f"File does not exist: {source}")
    if source.suffix.lower() == ".md":
        return source
    if source.suffix.lower() not in SUPPORTED_EXTRACT_EXTENSIONS:
        raise SlashToolError(f"Unsupported evaluation input type: {source.suffix}")
    output_path = root / RESULT_ROOT_NAME / "extract_docs" / f"{source.name}.md"
    if output_path.exists():
        return output_path
    return extract_file_to_markdown(raw_path, working_folder, context, progress=progress)


def build_evaluation_messages(standard_text: str, target_text: str, instruction: str = "") -> list[dict]:
    system_instruction = (
        "You are evaluating whether a target markdown document matches the criteria, facts, "
        "structure, and requirements expressed by a standard markdown document. "
        "Be strict, evidence-based, and cite concrete mismatches. "
        "Return markdown with: Summary, Pass/Fail, Matching Evidence, Mismatches, Missing Items, Recommended Fixes."
    )
    if instruction:
        system_instruction += f"\nEvaluation instruction: {instruction}"
    return [
        {"role": "system", "content": system_instruction},
        {
            "role": "user",
            "content": (
                "## Standard Markdown\n\n"
                f"{standard_text}\n\n"
                "## Target Markdown\n\n"
                f"{target_text}\n"
            ),
        },
    ]


def _evaluation_client(context: SlashToolContext):
    if context.llm_client is not None:
        return context.llm_client
    if context.llm_settings is None:
        raise SlashToolError("LLM settings are required for /evaluate_file.")
    client = OpenAICompatibleClient(context.llm_settings)
    context.llm_client = client
    return client


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "file"
