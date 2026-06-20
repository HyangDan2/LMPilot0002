# Slash Tool Prompt Instructions

HD2 LLM Communicator(OpenAI Compatible) loads these markdown files to change the default instructions that slash tools send to the LLM.

## How to Edit

- `evaluate_file.md`: edits the evaluator instructions for `/evaluate_file`.
- `use_file.md`: edits the document-grounded answer instructions for `/use_file`.
- Variables such as `{{instruction}}` are replaced with runtime values.
- Unknown variables are left unchanged.
- `---` frontmatter is optional. Only the body below frontmatter is sent to the LLM.

## Available Variables

`evaluate_file.md`

- `{{instruction}}`: the user-provided extra evaluation instruction or the default evaluation instruction
- `{{standard_name}}`: standard file name
- `{{target_name}}`: target file name

`use_file.md`

- `{{instruction}}`: the user-provided instruction or the default summary instruction
- `{{source_name}}`: source file name

## Recommended Rules

- Keep prompt text in English, except for the output-language requirement.
- Require user-facing LLM output to be Korean markdown.
- Do not use HTML tags such as `<br>`; use markdown line breaks instead. Slash tools also normalize HTML line break tags to real newlines as a safety pass.
- State the required output sections clearly.
- Tell the model not to guess when content is missing from the document.
- If you remove a variable name, that runtime context will no longer be included in the prompt.
