# HD2 LLM Communicator(OpenAI Compatible)

HD2 LLM Communicator(OpenAI Compatible) is a PySide6 desktop application for working with OpenAI-compatible chat backends, local `llama-server` endpoints, workspace documents, and local slash tools.

The current application is centered on interactive chat plus document-oriented local tools:

- Chat with an OpenAI-compatible `/v1/chat/completions` backend.
- Keep SQLite-backed local chat sessions.
- Select a current workspace folder from the GUI.
- Extract `.xlsx`, `.pptx`, `.pdf`, and `.docx` files into markdown.
- Evaluate one file against another with `/evaluate_file`.
- Query or summarize one file with `/use_file`.
- Save generated artifacts under `HD2_result`.
- Keep slash tool prompt templates editable under `prompts/`.

The current slash-tool harness is document-extraction and LLM-evaluation focused. The remaining terminal pipeline scans and parses documents, builds a knowledge map, and stops at planner JSON artifacts.

---

## Features

- PySide6 desktop GUI with session-based chat.
- OpenAI-compatible backend settings in the GUI.
- Optional local `llama-server` fallback modes.
- SQLite chat history and recent-message prompt windows.
- Session summary and RAG foundation tables.
- Workspace folder selection with supported file listing.
- Local slash tools:
  - `/extract_file`
  - `/evaluate_file`
  - `/evaluate_file --mock-test`
  - `/use_file`
  - `/save_last_output`
  - `/tool_help`
- Markdown chat export and latest-output copy.
- Artifact access tags for generated files under `HD2_result`.

---

## Run the GUI

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python run.py --config config.yaml
```

`config.yaml` is intentionally ignored by git. Keep machine-specific paths, local server URLs, API keys, and model names there. The checked-in `config.example.yaml` is the template.

---

## Application Name

The configured program name is:

```text
HD2 LLM Communicator(OpenAI Compatible)
```

The default window title is set through `window_title` in `config.example.yaml` and through the fallback value in `src/gui/config.py`.

---

## OpenAI-Compatible Backend

The app is configured for OpenAI-compatible chat completions by default.

In the GUI settings panel, configure:

- **Base URL**: for example `http://127.0.0.1:8000/v1` or `http://localhost:1234/v1`
- **API Key**: optional for local servers
- **Model Name**: the model ID exposed by your backend
- **Embedding Model**: optional model ID for `/v1/embeddings`

Use **Save Settings** to persist runtime connection settings to `openai_settings.json`. That file is ignored by git because it may contain secrets.

Use **Test Connection** to check `/models` first. If model listing is unavailable, the app falls back to a minimal chat-completion test when a model name is set.

---

## Configuration

Important settings in `config.example.yaml`:

```yaml
backend: "openai"
openai_base_url: ""
openai_api_key: ""
openai_model: ""
openai_embedding_model: ""
connection_settings_path: "openai_settings.json"
system_prompt: "You are a helpful assistant."
temperature: 0.7
n_predict: 2048
ctx_size: 128000
response_timeout: 300
db_path: "./data/app.db"
window_title: "HD2 LLM Communicator(OpenAI Compatible)"
recent_message_limit: 40
rag_top_k: 5
rag_min_score: 0.2
memory_context_char_limit: 4000
```

Legacy `llama-cli` settings are still present in the config template but are only used when `backend: "cli"`.

---

## Workspace Folder

Use **Select Workspace Folder** in the left sidebar to choose the current workspace folder for the selected chat session.

The GUI shows the selected session's workspace in the bottom status bar:

```text
Current Workspace Folder : <path>
```

If the selected session has no workspace, the status bar shows:

```text
Current Workspace Folder : -
```

Workspace folders are stored per chat session. Switching sessions also switches the active workspace folder and refreshes the attachment list for that session. Long workspace paths are compacted in the status bar and exposed in the tooltip.

The folder is selected even when it contains no supported files. The attachment list shows supported files directly inside the selected session's workspace folder; subfolders are not scanned for the GUI attachment list.

Supported GUI attachment file types:

```text
.txt .md .json .yaml .yml .csv .py .log .pdf .docx .pptx .png .jpg .jpeg .bmp .webp
```

Files are not automatically included in ordinary chat prompts. Double-click an item in the attachment list to insert its filename into the input box.

Use **Clear Workspace** to clear the selected session's workspace folder and attachment list.

---

## Local Slash Tools

Slash tools run from the prompt box and use the selected chat session's current workspace folder as their root. The workspace path is captured when a slash tool starts, so switching sessions while a tool runs does not change that running tool's root folder.

```text
/extract_file <xlsx|pptx|pdf|docx path>
/evaluate_file <standard markdown|file> <target markdown|file> [extra instruction]
/evaluate_file --mock-test
/use_file <markdown|file> [instruction]
/save_last_output
/tool_help
```

Path safety rules:

- User-provided paths are resolved inside the current workspace folder.
- Generated files are written under `HD2_result`.
- Slash tools do not read or write outside the current workspace folder.

### `/extract_file`

Extracts `.xlsx`, `.pptx`, `.pdf`, or `.docx` into markdown:

```text
<current-workspace-folder>/HD2_result/extract_docs/<filename>.md
```

### `/evaluate_file`

Evaluates a target markdown or source file against a standard markdown or source file.

If an input is a supported source file and no extracted markdown exists yet, the tool first runs the extraction procedure.

Reports are saved under:

```text
<current-workspace-folder>/HD2_result/evaluate_file/
```

Default instruction when no extra instruction is provided:

```text
Evaluate the content of <target> using <standard> as the standard.
```

### `/evaluate_file --mock-test`

Creates two mock files in the current workspace folder:

```text
Mock_Standard.md
Mock_Evaluation.md
```

Then it immediately evaluates the mock target document against the mock standard.

### `/use_file`

Answers from one markdown or source file. If the source file has not been extracted yet, the tool extracts it first.

Results are saved under:

```text
<current-workspace-folder>/HD2_result/use_file/YYMMDD_HHMMSS.md
```

Default instruction when no instruction is provided:

```text
Summarize the content of <source>.
```

Large markdown files currently stop with:

```text
Require chunk retrieval!
```

Chunk retrieval is intentionally left for a later update.

### `/save_last_output`

Saves the latest assistant or tool output:

```text
<current-workspace-folder>/HD2_result/save_last_output/YYMMDD_HHMMSS.md
```

### `/tool_help`

Shows slash tool help generated from `src/slash_tools/registry.py`.

---

## Slash Tool Prompt Templates

Prompt templates live under:

```text
prompts/evaluate_file.md
prompts/use_file.md
prompts/README.md
```

Prompt template text is written in English. The output language requirement remains fixed to Korean markdown through:

```yaml
output_language: ko
```

The templates may use these variables:

- `{{instruction}}`
- `{{standard_name}}`
- `{{target_name}}`
- `{{source_name}}`

Slash tools normalize HTML line break tags such as `<br>`, `<br/>`, and `<br />` to real newlines before saving or displaying LLM output.

---

## Generated Artifacts

During normal chat, the model can request previously generated artifacts from the current workspace folder. The app only allows access under:

```text
<current-workspace-folder>/HD2_result/
```

Supported tags:

```text
[read_output] extract_docs/a.xlsx.md [/read_output]
[list_outputs] extract_docs [/list_outputs]
```

Qwen-style generated-output aliases are also supported:

```text
[read_file] llm/extract_docs/a.xlsx.md [/read_file]
[read_file] HD2_result/extract_docs/a.xlsx.md [/read_file]
```

Paths are resolved inside the current workspace folder and cannot escape `HD2_result`.

---

## Memory and RAG Foundation

The GUI uses a recent-message window instead of reprocessing the full session on every send.

Available foundation pieces:

- `OpenAICompatibleClient.embeddings(...)` calls `/v1/embeddings`.
- `RagStore` stores chunk text, source metadata, and embedding vectors in SQLite.
- Cosine similarity search returns top-k relevant chunks.
- Retrieved chunks can be formatted and passed into model context.

The `/use_file` tool currently uses direct markdown input and does not yet perform chunk retrieval.

---

## Terminal Planning Pipeline

The remaining terminal pipeline is not the slash-tool document workflow.

It scans a working folder recursively, parses supported documents, writes normalized JSON, creates a knowledge map, and asks an OpenAI-compatible LLM for planner JSON. PPTX rendering has been removed from this harness.

Supported source files:

```text
.pptx .docx .xlsx .pdf
```

Run:

```bash
python -m src.main --working-dir data/working --output-dir data/outputs "Create a 7-slide executive summary"
```

Generated files:

```text
<normalized-dir>/<document-id>.json
<normalized-dir>/knowledge_map.md
<normalized-dir>/knowledge_map.json
<output-dir>/planner_output.json
```

---

## Architecture

```text
src/gui             PySide6 GUI, sessions, database, LLM client, artifact access
src/slash_tools     local prompt-box slash tools
src/ingestion       deterministic document scanning and parsers
src/transform       knowledge-map construction
src/planner         chunked planner JSON pipeline
src/models          shared parser/planner dataclasses
src/utils           path, IO, and logging helpers
prompts             editable slash tool prompt templates
docs                slash tool harness guide
```

High-level flow:

```text
GUI
  |
  |-- Chat sessions -> OpenAI-compatible chat backend
  |-- Workspace folder -> slash tools -> HD2_result
  |-- Artifact tags -> safe reads under HD2_result
  |-- SQLite -> messages, summaries, RAG chunks
```

---

## Troubleshooting

### Backend connection fails

- Confirm the Base URL includes `/v1` when required by your backend.
- Confirm the model name matches the backend's exposed model ID.
- Use **Test Connection** in the GUI.

### Output is too short

- Increase `n_predict`.
- Confirm the backend is using chat completions when available.

### Large file tool call fails

If `/evaluate_file` or `/use_file` reports `Require chunk retrieval!`, the extracted markdown is too large for direct LLM input. Chunk retrieval is planned as a later update.

### Broken characters

The GUI applies Unicode normalization and unsupported-character filtering before display.
