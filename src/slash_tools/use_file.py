from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .context import SlashToolContext
from .errors import SlashToolError
from .evaluate_file import _evaluation_client, ensure_markdown_for_input
from .path_safety import output_root, require_working_folder
from .results import SlashToolResult


def use_file_command(
    args: list[str],
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress=None,
) -> SlashToolResult:
    if not args:
        raise SlashToolError("Usage: /use_file <markdown|file> [instruction]")

    root = require_working_folder(working_folder)
    source_arg = args[0]
    instruction = " ".join(args[1:]).strip() or f"{Path(source_arg).name}의 내용을 요약하라"
    markdown_path = ensure_markdown_for_input(source_arg, root, working_folder, context, progress)
    markdown_text = markdown_path.read_text(encoding="utf-8", errors="replace")
    messages = build_use_file_messages(Path(source_arg).name, markdown_text, instruction)

    if progress is not None:
        progress("status", "Using extracted markdown with LLM...")
    context.check_cancelled()
    client = _evaluation_client(context)
    answer = client.chat_completion(messages)

    out_dir = output_root(root, "use_file")
    output_path = out_dir / f"{datetime.now().strftime('%y%m%d_%H%M%S')}.md"
    output_path.write_text(
        "\n".join(
            [
                f"# Use File: {Path(source_arg).name}",
                "",
                f"- Source Markdown: `{markdown_path}`",
                "",
                "## Instruction",
                "",
                instruction,
                "",
                "## LLM Output",
                "",
                answer.strip(),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return SlashToolResult(
        text=f"Use-file output saved:\n{output_path}\n\n{answer.strip()}",
        tool_name="/use_file",
    )


def build_use_file_messages(source_name: str, markdown_text: str, instruction: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You answer using only the provided extracted markdown document. "
                "If the requested information is not present, say that it is not present in the document. "
                "Return concise markdown and cite visible section, page, slide, or sheet headings when possible."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Instruction: {instruction}\n\n"
                f"## Extracted Markdown From {source_name}\n\n"
                f"{markdown_text}"
            ),
        },
    ]
