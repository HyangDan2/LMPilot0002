from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .context import SlashToolContext
from .errors import SlashToolError
from .evaluate_file import _evaluation_client, ensure_markdown_for_input, read_markdown_for_direct_llm
from .path_safety import output_root, require_working_folder
from .prompt_loader import render_prompt
from .results import SlashToolResult, normalize_markdown_output


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
    instruction = " ".join(args[1:]).strip() or f"Summarize the content of {Path(source_arg).name}."
    markdown_path = ensure_markdown_for_input(source_arg, root, working_folder, context, progress)
    markdown_text = read_markdown_for_direct_llm(markdown_path)
    messages = build_use_file_messages(Path(source_arg).name, markdown_text, instruction)

    if progress is not None:
        progress("status", "Generating an LLM response from the extracted markdown...")
    context.check_cancelled()
    client = _evaluation_client(context)
    answer = normalize_markdown_output(client.chat_completion(messages)).strip()

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
                answer,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return SlashToolResult(
        text=f"File-based response saved:\n{output_path}\n\n{answer}",
        tool_name="/use_file",
    )


def build_use_file_messages(source_name: str, markdown_text: str, instruction: str) -> list[dict]:
    fallback_instruction = (
        "Answer using only the provided extracted markdown document. "
        "If the requested information is not present in the document, state clearly that it is not present. "
        "Answer concisely in Korean markdown. Do not use HTML tags such as <br>; use markdown line breaks instead. "
        "When possible, cite visible section, page, slide, or sheet titles as evidence."
    )
    system_instruction = render_prompt(
        "use_file",
        {
            "instruction": instruction,
            "source_name": source_name,
        },
        fallback_instruction,
    )
    return [
        {
            "role": "system",
            "content": system_instruction,
        },
        {
            "role": "user",
            "content": (
                f"Instruction: {instruction}\n\n"
                f"## Extracted Markdown from {source_name}\n\n"
                f"{markdown_text}"
            ),
        },
    ]
