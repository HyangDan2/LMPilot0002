from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .context import SlashToolContext
from .errors import SlashToolError
from .evaluate_file import evaluate_file_command
from .extract_file import extract_file_command
from .help import tool_help_command
from .save_last_output import save_last_output_command
from .use_file import use_file_command
from .results import SlashToolResult, error_result


SlashProgressCallback = Callable[[str, str], None]
SlashHandler = Callable[[list[str], str | Path | None, SlashToolContext, SlashProgressCallback | None], SlashToolResult]


@dataclass(frozen=True)
class SlashTool:
    name: str
    description: str
    usage: str
    handler: SlashHandler
    examples: list[str] = field(default_factory=list)


SLASH_TOOLS: dict[str, SlashTool] = {
    "/extract_file": SlashTool(
        name="/extract_file",
        description="xlsx, pptx, pdf, docx 파일을 HD2_result/extract_docs 아래 markdown으로 추출합니다.",
        usage="/extract_file <file>",
        handler=extract_file_command,
        examples=["/extract_file a.xlsx", "/extract_file 'deck review.pptx'"],
    ),
    "/evaluate_file": SlashTool(
        name="/evaluate_file",
        description="기준 markdown 또는 파일을 바탕으로 평가 대상 markdown 또는 파일을 LLM으로 평가합니다. --mock-test로 샘플 평가를 실행할 수 있습니다.",
        usage="/evaluate_file <기준 markdown|파일> <평가대상 markdown|파일> [추가 지시] 또는 /evaluate_file --mock-test",
        handler=evaluate_file_command,
        examples=["/evaluate_file a.xlsx b.pptx 해당 내용이 제대로 구성되어 있는지 확인하라", "/evaluate_file --mock-test"],
    ),
    "/use_file": SlashTool(
        name="/use_file",
        description="하나의 markdown 또는 원본 파일을 근거로 LLM 답변을 생성합니다. 필요하면 먼저 파일을 추출합니다.",
        usage="/use_file <markdown|파일> [지시]",
        handler=use_file_command,
        examples=["/use_file a.xlsx 해당 파일에서 quantitative result를 찾아서 요약하라", "/use_file a.xlsx"],
    ),
    "/save_last_output": SlashTool(
        name="/save_last_output",
        description="최근 assistant 또는 tool 출력을 HD2_result/save_last_output 아래에 저장합니다.",
        usage="/save_last_output",
        handler=save_last_output_command,
        examples=["/save_last_output"],
    ),
    "/tool_help": SlashTool(
        name="/tool_help",
        description="사용 가능한 로컬 slash tool 도움말을 표시합니다.",
        usage="/tool_help",
        handler=tool_help_command,
        examples=["/tool_help"],
    ),
}


def run_slash_command(
    command_text: str,
    working_folder: str | Path | None,
    context: SlashToolContext,
    progress: SlashProgressCallback | None = None,
) -> SlashToolResult | None:
    stripped = command_text.strip()
    if not stripped.startswith("/"):
        return None
    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        return error_result(f"malformed slash command: {exc}")
    if not parts:
        return None
    command = parts[0]
    tool = SLASH_TOOLS.get(command)
    if tool is None:
        return error_result(f"알 수 없는 slash command입니다: '{command}'. 사용 가능한 명령은 /tool_help로 확인하세요.", command)
    try:
        return tool.handler(parts[1:], working_folder, context, progress)
    except SlashToolError as exc:
        return error_result(str(exc), command)
