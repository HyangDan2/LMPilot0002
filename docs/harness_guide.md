# Slash Tool Harness Guide

This project keeps local prompt-box tools under `src/slash_tools`.
Agents adding new tools should follow this harness instead of creating one-off GUI branches.

## Tool Contract

Every tool is registered in `src/slash_tools/registry.py` as a `SlashTool` with:

- `name`: command name, including the leading slash
- `description`: one short user-facing sentence
- `usage`: exact command syntax
- `handler`: callable with `(args, working_folder, context, progress)`
- `examples`: short command examples shown by `/tool_help`

After registration, `/tool_help` must show the new tool automatically.

## Handler Rules

Tool handlers must:

- Accept already-tokenized `args` from `shlex.split`.
- Use `SlashToolError` for user-correctable failures.
- Use `SlashToolContext.check_cancelled()` inside loops or before long work.
- Return `SlashToolResult`.
- Write generated files only under `<current-workspace-folder>/HD2_result/<tool-folder>/`.
- Never read or write outside the current workspace folder unless the user explicitly changes the harness.
- Use Korean for user-facing results, progress text, recoverable errors, and default LLM prompts.
- Use markdown line breaks for user-facing output. Do not rely on HTML `<br>` tags; `SlashToolResult` normalizes HTML line break tags to real newlines as a final safety pass.

## Path Safety

Use helpers from `src/slash_tools/path_safety.py`:

- `require_working_folder` for commands that need a current workspace folder.
- `resolve_inside` for any user-provided path.
- `output_root` for generated output directories.

Do not hand-roll path traversal checks in each tool.

## Current Tools

`/extract_file <file>`

Extracts `.xlsx`, `.pptx`, `.pdf`, or `.docx` into markdown at:

```text
<current-workspace-folder>/HD2_result/extract_docs/<filename>.md
```

`/evaluate_file <standard markdown|file> <target markdown|file> [extra prompt]`

Ensures both inputs are markdown. If either input is a supported source file and has not been extracted yet, it first runs the extraction procedure. It then asks the configured LLM to judge the target against the standard and writes:

```text
<current-workspace-folder>/HD2_result/evaluate_file/<standard>__vs__<target>.md
```

When no extra prompt is provided, the default prompt is:

```text
<argument1>의 기준으로 <argument2>의 파일의 내용을 평가하라
```

`/evaluate_file --mock-test`

Creates two mock files in the current workspace folder and immediately runs evaluation:

```text
Mock_Standard.md
Mock_Evaluation.md
```

`Mock_Standard.md` contains 10 presence/absence evaluation criteria. `Mock_Evaluation.md` is a normal technical document that intentionally satisfies about 80% of the criteria so the evaluation flow can be tested quickly.

`/use_file <markdown|file> [instruction]`

Ensures the input is markdown, extracting supported source files first when needed. It sends the extracted markdown and instruction to the configured LLM, then writes:

```text
<current-workspace-folder>/HD2_result/use_file/YYMMDD_HHMMSS.md
```

When no instruction is provided, the default prompt is:

```text
<argument1>의 내용을 요약하라
```

`/save_last_output`

Saves the latest assistant or tool output from the current session to:

```text
<current-workspace-folder>/HD2_result/save_last_output/YYMMDD_HHMMSS.md
```

`/tool_help`

Renders help from registry metadata.

## LLM Prompt Layering

For tools that call an LLM:

- Put stable behavior in a prompt markdown file under `prompts/<tool_name>.md` when practical.
- Use `src/slash_tools/prompt_loader.py` to load prompt markdown and render variables.
- Keep a Korean fallback prompt in code so the tool still works when the prompt file is missing.
- Tell the LLM to avoid HTML tags such as `<br>` and use markdown line breaks instead.
- Put source artifacts in the user message.
- Append free-form user instructions as an additional prompt layer, not by rewriting extracted content.
- Save the LLM result to `HD2_result/<tool-folder>/` and include the saved path in `SlashToolResult.text`.

Current prompt config files:

```text
prompts/evaluate_file.md
prompts/use_file.md
```

Prompt markdown may include optional frontmatter. Only the body below frontmatter is sent to the LLM. Supported variables are documented in `prompts/README.md`.

## Tests

Add or update tests whenever a tool changes:

- Registry/help behavior.
- Path traversal rejection.
- Output path convention.
- Auto prerequisite behavior.
- LLM prompt content when a tool calls the model.

Prefer small generated fixtures in temporary directories.
