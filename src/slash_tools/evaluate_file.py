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
REQUIRE_CHUNK_RETRIEVAL_MESSAGE = "Require chunk retrieval! 추출된 markdown이 직접 LLM에 넣기에는 너무 큽니다."
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
        raise SlashToolError("사용법: /evaluate_file <기준 markdown|파일> <평가대상 markdown|파일> [추가 지시]")

    root = require_working_folder(working_folder)
    standard_source = args[0]
    target_source = args[1]
    instruction = " ".join(args[2:]).strip() or (
        f"{Path(standard_source).name}의 기준으로 {Path(target_source).name}의 파일의 내용을 평가하라"
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
        progress("status", "추출된 markdown을 기준으로 LLM 평가를 실행하는 중...")
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
                "## 평가 지시",
                "",
                instruction,
                "",
                "## LLM 평가 결과",
                "",
                answer,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return SlashToolResult(
        text=f"평가 결과가 저장되었습니다:\n{output_path}\n\n{answer}",
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
        raise SlashToolError(f"파일이 존재하지 않습니다: {source}")
    if source.suffix.lower() == ".md":
        return source
    if source.suffix.lower() not in SUPPORTED_EXTRACT_EXTENSIONS:
        raise SlashToolError(f"평가 입력으로 지원하지 않는 파일 형식입니다: {source.suffix}")
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
    standard_name: str = "기준 문서",
    target_name: str = "평가 대상 문서",
) -> list[dict]:
    fallback_instruction = (
        "당신은 기준 markdown 문서에 포함된 평가 기준, 사실, 구조, 요구사항을 바탕으로 "
        "평가 대상 markdown 문서가 기준을 충족하는지 판단하는 평가자입니다. "
        "반드시 한국어 markdown으로 답변하고, 근거가 있는 항목과 없는 항목을 엄격히 구분하세요. "
        "HTML 태그(<br> 등)를 쓰지 말고 markdown 줄바꿈을 사용하세요. "
        "출력 섹션은 다음을 포함하세요: 요약, 통과/미통과 판단, 충족 항목, 미충족 항목, 근거, 개선 제안."
    )
    if instruction:
        fallback_instruction += f"\n평가 지시: {instruction}"
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
                "## 기준 Markdown\n\n"
                f"{standard_text}\n\n"
                "## 평가 대상 Markdown\n\n"
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
    return """# Mock Standard 평가 기준

아래 10개 항목은 평가 대상 기술 문서에 해당 내용이 존재하는지 확인하기 위한 기준이다.

| 번호 | 평가 항목 |
| --- | --- |
| 1 | 문서에 목적과 범위가 있는지? |
| 2 | 문서에 시스템 아키텍처 설명이 있는지? |
| 3 | 문서에 주요 컴포넌트 설명이 있는지? |
| 4 | 문서에 API 또는 인터페이스 설명이 있는지? |
| 5 | 문서에 데이터 흐름 설명이 있는지? |
| 6 | 문서에 정량적 성능 결과가 있는지? |
| 7 | 문서에 보안 고려사항이 있는지? |
| 8 | 문서에 운영 및 배포 절차가 있는지? |
| 9 | 문서에 장애 대응 또는 복구 전략이 있는지? |
| 10 | 문서에 제한사항 및 향후 과제가 있는지? |
"""


def _mock_evaluation_markdown() -> str:
    return """# Mock 기술 문서: Insight Pipeline

## 목적과 범위

Insight Pipeline은 사내 문서와 표 데이터를 수집하여 분석용 markdown으로 변환하고, 사용자가 질문한 주제에 맞춰 요약 결과를 제공하는 시스템이다. 본 문서는 MVP 범위의 수집, 변환, 평가 흐름을 설명한다.

## 시스템 아키텍처

시스템은 Desktop GUI, Slash Tool Harness, File Extraction Layer, LLM Adapter, Result Store로 구성된다. GUI는 사용자의 명령을 받고, Slash Tool Harness는 명령을 검증한 뒤 파일 추출 또는 LLM 호출을 실행한다.

## 주요 컴포넌트

- GUI Controller: 세션, 첨부 폴더, 사용자 입력을 관리한다.
- Extract File Tool: xlsx, pptx, pdf, docx 파일을 markdown으로 변환한다.
- Evaluate File Tool: 기준 문서와 평가 대상 문서를 비교한다.
- Result Store: 생성된 결과를 HD2_result 하위에 저장한다.

## API 및 인터페이스

사용자는 `/extract_file`, `/evaluate_file`, `/use_file`, `/save_last_output` 명령을 통해 기능을 호출한다. 각 명령은 파일 경로와 자연어 지시를 인자로 받는다.

## 데이터 흐름

사용자가 파일 기반 명령을 실행하면 입력 파일은 markdown으로 추출된다. 추출된 markdown은 LLM prompt에 포함되고, LLM 응답은 결과 저장소에 markdown 파일로 기록된다.

## 정량적 성능 결과

| 항목 | 결과 |
| --- | --- |
| xlsx 20행 추출 시간 | 0.3초 |
| pptx 12슬라이드 추출 시간 | 1.1초 |
| 평균 LLM 평가 응답 시간 | 4.8초 |
| mock 기준 충족률 | 80% |

## 운영 및 배포 절차

운영자는 Python 의존성을 설치한 뒤 데스크톱 앱을 실행한다. 사용자는 작업 폴더를 첨부하고 slash command를 입력해 결과물을 생성한다. 결과물은 HD2_result 폴더 아래에서 확인한다.

## 제한사항 및 향후 과제

현재 긴 markdown은 직접 LLM에 입력하기 어렵기 때문에 큰 파일은 chunk retrieval이 필요하다. 향후에는 chunk 분할, 검색, 근거 기반 답변을 추가할 계획이다.
"""


def _evaluation_client(context: SlashToolContext):
    if context.llm_client is not None:
        return context.llm_client
    if context.llm_settings is None:
        raise SlashToolError("/evaluate_file 실행에는 LLM 설정이 필요합니다.")
    client = OpenAICompatibleClient(context.llm_settings)
    context.llm_client = client
    return client


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "file"
