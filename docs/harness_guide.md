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
- Write generated files only under `<attached-folder>/HD2_result/<tool-folder>/`.
- Never read or write outside the attached folder unless the user explicitly changes the harness.

## Path Safety

Use helpers from `src/slash_tools/path_safety.py`:

- `require_working_folder` for commands that need an attached folder.
- `resolve_inside` for any user-provided path.
- `output_root` for generated output directories.

Do not hand-roll path traversal checks in each tool.

## Current Tools

`/extract_file <file>`

Extracts `.xlsx`, `.pptx`, `.pdf`, or `.docx` into markdown at:

```text
<attached-folder>/HD2_result/extract_docs/<filename>.md
```

`/evaluate_file <standard markdown|file> <target markdown|file> [extra prompt]`

Ensures both inputs are markdown. If either input is a supported source file and has not been extracted yet, it first runs the extraction procedure. It then asks the configured LLM to judge the target against the standard and writes:

```text
<attached-folder>/HD2_result/evaluate_file/<standard>__vs__<target>.md
```

When no extra prompt is provided, the default prompt is:

```text
<argument1>의 기준으로 <argument2>의 파일의 내용을 평가하라
```

`/use_file <markdown|file> [instruction]`

Ensures the input is markdown, extracting supported source files first when needed. It sends the extracted markdown and instruction to the configured LLM, then writes:

```text
<attached-folder>/HD2_result/use_file/YYMMDD_HHMMSS.md
```

When no instruction is provided, the default prompt is:

```text
<argument1>의 내용을 요약하라
```

`/save_last_output`

Saves the latest assistant or tool output from the current session to:

```text
<attached-folder>/HD2_result/save_last_output/YYMMDD_HHMMSS.md
```

`/tool_help`

Renders help from registry metadata.

## LLM Prompt Layering

For tools that call an LLM:

- Put stable behavior in the system message.
- Put source artifacts in the user message.
- Append free-form user instructions as an additional prompt layer, not by rewriting extracted content.
- Save the LLM result to `HD2_result/<tool-folder>/` and include the saved path in `SlashToolResult.text`.

## Tests

Add or update tests whenever a tool changes:

- Registry/help behavior.
- Path traversal rejection.
- Output path convention.
- Auto prerequisite behavior.
- LLM prompt content when a tool calls the model.

Prefer small generated fixtures in temporary directories.
