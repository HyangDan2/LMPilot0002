from __future__ import annotations

import re
from pathlib import Path

from src.gui.llm_client import OpenAICompatibleClient

from .context import SlashToolContext
from .errors import SlashToolError
from .extract_file import SUPPORTED_EXTRACT_EXTENSIONS, extract_file_to_markdown
from .path_safety import RESULT_ROOT_NAME, output_root, require_working_folder, resolve_inside
from .prompt_loader import render_prompt
from .results import SlashToolResult, normalize_markdown_output

MAX_DIRECT_MARKDOWN_CHARS = 120_000
REQUIRE_CHUNK_RETRIEVAL_MESSAGE = "Require chunk retrieval! The extracted markdown is too large to send directly to the LLM."
MOCK_STANDARD_FILENAME = "Mock_Standard.md"
MOCK_EVALUATION_FILENAME = "Mock_Evaluation.md"


def evaluate_file_command(
    args: list[str],
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress=None,
) -> SlashToolResult:
    if args == ["--mock-test"]:
        root = require_working_folder(working_folder)
        create_mock_evaluation_files(root)
        return evaluate_file_command(
            [MOCK_STANDARD_FILENAME, MOCK_EVALUATION_FILENAME],
            working_folder,
            context,
            progress=progress,
        )

    if len(args) < 2:
        raise SlashToolError("Usage: /evaluate_file <standard markdown|file> <target markdown|file> [extra instruction]")

    root = require_working_folder(working_folder)
    standard_source = args[0]
    target_source = args[1]
    instruction = " ".join(args[2:]).strip() or (
        f"Evaluate the content of {Path(target_source).name} using {Path(standard_source).name} as the standard."
    )

    standard_markdown = ensure_markdown_for_input(standard_source, root, working_folder, context, progress)
    target_markdown = ensure_markdown_for_input(target_source, root, working_folder, context, progress)

    standard_text = read_markdown_for_direct_llm(standard_markdown)
    target_text = read_markdown_for_direct_llm(target_markdown)
    messages = build_evaluation_messages(
        standard_text,
        target_text,
        instruction,
        standard_name=Path(standard_source).name,
        target_name=Path(target_source).name,
    )

    if progress is not None:
        progress("status", "Evaluating the extracted markdown with the LLM...")
    context.check_cancelled()
    client = _evaluation_client(context)
    answer = normalize_markdown_output(client.chat_completion(messages)).strip()

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
                "## Evaluation Instruction",
                "",
                instruction,
                "",
                "## LLM Evaluation Result",
                "",
                answer,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return SlashToolResult(
        text=f"Evaluation result saved:\n{output_path}\n\n{answer}",
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


def read_markdown_for_direct_llm(path: Path, max_chars: int = MAX_DIRECT_MARKDOWN_CHARS) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        raise SlashToolError(f"{REQUIRE_CHUNK_RETRIEVAL_MESSAGE} File: {path}")
    return text


def build_evaluation_messages(
    standard_text: str,
    target_text: str,
    instruction: str = "",
    standard_name: str = "standard document",
    target_name: str = "target document",
) -> list[dict]:
    fallback_instruction = (
        "You are an evaluator who judges whether the target markdown document satisfies the criteria, facts, "
        "structure, and requirements contained in the standard markdown document. "
        "Answer in Korean markdown. Strictly distinguish items with evidence from items without evidence. "
        "Do not use HTML tags such as <br>; use markdown line breaks instead. "
        "Include these output sections: Summary, Pass/Fail Judgment, Satisfied Items, Unsatisfied Items, Evidence, Improvement Suggestions."
    )
    if instruction:
        fallback_instruction += f"\nEvaluation instruction: {instruction}"
    system_instruction = render_prompt(
        "evaluate_file",
        {
            "instruction": instruction,
            "standard_name": standard_name,
            "target_name": target_name,
        },
        fallback_instruction,
    )
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


def create_mock_evaluation_files(root: Path) -> tuple[Path, Path]:
    standard_path = root / MOCK_STANDARD_FILENAME
    evaluation_path = root / MOCK_EVALUATION_FILENAME
    standard_path.write_text(_mock_standard_markdown(), encoding="utf-8")
    evaluation_path.write_text(_mock_evaluation_markdown(), encoding="utf-8")
    return standard_path, evaluation_path


def _mock_standard_markdown() -> str:
    return """# Mock Standard Evaluation Criteria

The following 10 criteria check whether the target technical document contains the required content.

| No. | Evaluation Criterion |
| --- | --- |
| 1 | Does the document include purpose and scope? |
| 2 | Does the document describe the system architecture? |
| 3 | Does the document describe the main components? |
| 4 | Does the document describe APIs or interfaces? |
| 5 | Does the document describe the data flow? |
| 6 | Does the document include quantitative performance results? |
| 7 | Does the document include security considerations? |
| 8 | Does the document include operations and deployment procedures? |
| 9 | Does the document include incident response or recovery strategy? |
| 10 | Does the document include limitations and future work? |
"""


def _mock_evaluation_markdown() -> str:
    return """# Mock Technical Document: Insight Pipeline

## Purpose and Scope

Insight Pipeline is a system that collects internal documents and tabular data, converts them into analysis-ready markdown, and provides summary results aligned with a user's question. This document describes the MVP scope for collection, conversion, and evaluation flows.

## System Architecture

The system consists of a Desktop GUI, Slash Tool Harness, File Extraction Layer, LLM Adapter, and Result Store. The GUI receives user commands, and the Slash Tool Harness validates commands before running file extraction or LLM calls.

## Main Components

- GUI Controller: manages sessions, the workspace folder, and user input.
- Extract File Tool: converts xlsx, pptx, pdf, and docx files into markdown.
- Evaluate File Tool: compares a standard document with a target document.
- Result Store: stores generated results under HD2_result.

## APIs and Interfaces

Users call features through `/extract_file`, `/evaluate_file`, `/use_file`, and `/save_last_output`. Each command accepts file paths and natural-language instructions as arguments.

## Data Flow

When a user runs a file-based command, the input file is extracted into markdown. The extracted markdown is included in the LLM prompt, and the LLM response is written as a markdown file in the result store.

## Quantitative Performance Results

| Item | Result |
| --- | --- |
| xlsx 20-row extraction time | 0.3 seconds |
| pptx 12-slide extraction time | 1.1 seconds |
| average LLM evaluation response time | 4.8 seconds |
| mock criteria satisfaction rate | 80% |

## Operations and Deployment Procedures

Operators install Python dependencies and run the desktop app. Users select a workspace folder and enter slash commands to generate outputs. Results are available under the HD2_result folder.

## Limitations and Future Work

Long markdown files are currently difficult to send directly to the LLM, so large files require chunk retrieval. Future work includes chunk splitting, retrieval, and evidence-grounded answers.
"""


def _evaluation_client(context: SlashToolContext):
    if context.llm_client is not None:
        return context.llm_client
    if context.llm_settings is None:
        raise SlashToolError("LLM settings are required to run /evaluate_file.")
    client = OpenAICompatibleClient(context.llm_settings)
    context.llm_client = client
    return client


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "file"
