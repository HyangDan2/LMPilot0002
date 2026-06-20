# Slash Tool Prompt Instructions

이 폴더의 markdown 파일을 수정하면 slash tool이 LLM에 전달하는 기본 지시를 바꿀 수 있습니다.

## 수정 방법

- `evaluate_file.md`: `/evaluate_file` 평가자 지시를 수정합니다.
- `use_file.md`: `/use_file` 문서 기반 답변 지시를 수정합니다.
- `{{instruction}}` 같은 변수는 실행 시 실제 값으로 치환됩니다.
- 알 수 없는 변수는 그대로 남습니다.
- `---` frontmatter는 있어도 되고 없어도 됩니다. 실제 LLM에는 frontmatter 아래 본문만 전달됩니다.

## 사용 가능한 변수

`evaluate_file.md`

- `{{instruction}}`: 사용자가 입력한 추가 평가 지시 또는 기본 평가 지시
- `{{standard_name}}`: 기준 파일 이름
- `{{target_name}}`: 평가 대상 파일 이름

`use_file.md`

- `{{instruction}}`: 사용자가 입력한 지시 또는 기본 요약 지시
- `{{source_name}}`: 사용할 파일 이름

## 권장 규칙

- 사용자-facing 출력은 한국어 markdown을 기준으로 작성하세요.
- HTML 태그(`<br>` 등)를 사용하지 말고 markdown 줄바꿈을 사용하세요. Slash tool은 안전장치로 HTML 줄바꿈 태그를 실제 줄바꿈으로 정규화합니다.
- 필요한 출력 섹션을 명확히 적으세요.
- 문서에 없는 내용은 추측하지 말라고 명시하세요.
- 변수명을 지우면 해당 실행 맥락이 prompt에 들어가지 않습니다.
