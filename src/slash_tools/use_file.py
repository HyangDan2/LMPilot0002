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
        raise SlashToolError("사용법: /use_file <markdown|파일> [지시]")

    root = require_working_folder(working_folder)
    source_arg = args[0]
    instruction = " ".join(args[1:]).strip() or f"{Path(source_arg).name}의 내용을 요약하라"
    markdown_path = ensure_markdown_for_input(source_arg, root, working_folder, context, progress)
    markdown_text = read_markdown_for_direct_llm(markdown_path)
    messages = build_use_file_messages(Path(source_arg).name, markdown_text, instruction)

    if progress is not None:
        progress("status", "추출된 markdown을 바탕으로 LLM 응답을 생성하는 중...")
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
                "## 지시",
                "",
                instruction,
                "",
                "## LLM 출력",
                "",
                answer,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return SlashToolResult(
        text=f"파일 기반 응답이 저장되었습니다:\n{output_path}\n\n{answer}",
        tool_name="/use_file",
    )


def build_use_file_messages(source_name: str, markdown_text: str, instruction: str) -> list[dict]:
    fallback_instruction = (
        "제공된 추출 markdown 문서만 근거로 사용해 답변하세요. "
        "요청한 정보가 문서에 없으면 문서에 없다고 명확히 말하세요. "
        "반드시 한국어 markdown으로 간결하게 답변하고, HTML 태그(<br> 등)를 쓰지 말고 markdown 줄바꿈을 사용하세요. "
        "가능하면 보이는 섹션, 페이지, 슬라이드, 시트 제목을 근거로 언급하세요."
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
                f"지시: {instruction}\n\n"
                f"## {source_name}에서 추출한 Markdown\n\n"
                f"{markdown_text}"
            ),
        },
    ]
