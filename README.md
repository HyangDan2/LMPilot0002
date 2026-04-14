# Gemma Console GUI (PySide6 MVP)

A lightweight OOP-based PySide6 desktop GUI for interacting with a local `llama-server`.

Designed for Raspberry Pi / Linux environments with stability-focused output handling.

---

## ✨ Features

* 🖥️ PySide6 desktop GUI (clean chat interface)
* 🔁 Local `llama-server` HTTP backend
  * Tries `/v1/chat/completions` first
  * Falls back to `/completion` with Gemma turn markers when chat completions are unavailable
* 💾 SQLite-based local chat history
* 🧹 ANSI / help banner / control sequence cleanup
* 🔤 Unicode normalization (`/uXXXX`, `\\uXXXX`) support
* 🚫 Emoji & unsupported glyph filtering (prevents rendering issues on Pi)
* ⚡ Multi-threaded inference (UI never freezes)
* ⌨️ **Keyboard shortcut**

  * `Ctrl + Enter` → Send message
* 🗂️ Session management

  * Create new session
  * Delete selected session
* 🧮 Local tool command

  * `/calc 2 + 3 * 4` runs the built-in calculator without calling the model backend

---

## 🧠 Behavior Changes (Important)

* ❌ **No auto session creation on startup**

  * User must manually click **"New Chat"**
* 🧭 Startup message:

  ```
  Select a session or click New Chat.
  ```
* 🧩 Prompt handling is history-aware:

  * Recent session messages are included in the model request.
  * Older context can be carried through a stored session summary.
  * Long context is trimmed from oldest turns first.
  * Multiline pasted text, code, logs, JSON, and YAML are preserved as much as practical.
* 🛑 Stop behavior:

  * The Stop button interrupts the current request and returns the UI to an idle state.
  * The next send should work without restarting the app.

---

## 🗂️ Session Management

* **New Chat**

  * Creates a new session in SQLite
* **Delete Session**

  * Deletes:

    * session
    * all associated messages
* UI auto-refresh after deletion

---

## 🚀 Run

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
# edit config.yaml for your local server/model settings
# keep server_endpoint: "auto" unless you intentionally force an endpoint
llama-server -m /path/to/your/model.gguf --host 127.0.0.1 --port 8080
python run.py --config config.yaml
```

`config.yaml` is intentionally ignored by git. Keep machine-specific paths and local server settings there. The checked-in `config.example.yaml` is the template.

---

## ⚙️ Configuration

* **llama-server URL**

  ```
  http://127.0.0.1:8080
  ```

* **llama-server endpoint**

  ```
  auto
  ```

  `auto` is recommended. The app tries `/v1/chat/completions` first, then falls back to `/completion`.

  The app also accepts `/auto` and treats it the same as `auto`, but `auto` is clearer in config files.

* **Model (GGUF)**

  ```
  /path/to/your/gemma-3-1b-it-Q4_K_M.gguf
  ```

* **System prompt**

  ```yaml
  system_prompt: "You are a helpful assistant."
  ```

  In server mode, this is sent as the first structured system message when `/v1/chat/completions` is used. In `/completion` fallback mode, it is included in the Gemma-template prompt.

* **Response length**

  ```yaml
  n_predict: 512
  response_token_reserve: 256
  max_prompt_chars: 12000
  recent_message_limit: 40
  memory_context_char_limit: 4000
  ```

  If answers are too short, increase `n_predict`. If long pasted prompts are being trimmed too aggressively, increase `ctx_size` and `max_prompt_chars` in line with your model/server capacity.

* **Conversation memory**

  ```yaml
  recent_message_limit: 40
  rag_top_k: 5
  rag_min_score: 0.2
  openai_embedding_model: ""
  ```

  The prompt builder uses a recent-message window instead of reprocessing the entire session on every send. The database also has a session summary table and a vector chunk store so future RAG flows can combine a rolling summary, retrieved memory, recent messages, and the current user prompt.

* **Local tools**

  The first built-in local tool is a safe calculator command:

  ```text
  /calc 2 + 3 * 4
  /calculator (2 + 3) * 4
  ```

  Tool commands run locally before any backend validation, so the calculator works even when the OpenAI-compatible backend is not connected. Results are displayed as `[Tool]` messages and saved in chat history.

  Tools are registered as dictionaries under `src/tools`. Each registry entry includes a name, description, parameter metadata, an OpenAI-compatible schema stub, and a handler. This keeps the current manual command path small while leaving a clean route to future model-driven tool calling.

Create and modify local settings in:

```bash
cp config.example.yaml config.yaml
```

---

## 🧩 Architecture Overview

```
GUI (PySide6)
   │
   ├── QThread (ChatWorker)
   │       │
   │       └── LlamaServerSession (HTTP)
   │              ├── /v1/chat/completions (preferred)
   │              └── /completion (Gemma-template fallback)
   │
   ├── SQLite (ChatRepository)
   │      ├── recent message window
   │      └── session summary memory
   │
   ├── RAG Store
   │      ├── OpenAI-compatible /v1/embeddings
   │      └── cosine similarity search
   │
   ├── Local Tools
   │      ├── dict-based registry in src/tools
   │      └── calculator command (/calc)
   │
   └── Text Processing
          ├── ANSI strip
          ├── Unicode normalize
          └── Glyph filtering
```

---

## ⚠️ Notes (Raspberry Pi)

* Emoji may break rendering → filtered by design
* Ensure `llama-server` runs independently before GUI
* If output looks corrupted:

  * Check locale (`UTF-8`)
  * Verify terminal encoding

---

## 🔧 Troubleshooting

### 1. Model not loading

* Check your local `config.yaml` paths.
* Verify the `.gguf` file exists.
* `config.example.yaml` is only a template; copy it to `config.yaml` and edit it before running.

---

### 2. llama-server error

```bash
curl http://127.0.0.1:8080/health
```

→ confirm the server is reachable

If you see an error like:

```text
llama-server returned HTTP 404 from /auto
```

Update to the latest branch and set:

```yaml
server_endpoint: "auto"
```

The current code treats both `auto` and `/auto` as automatic endpoint selection, but `auto` is the recommended spelling.

---

### 3. No response / stuck

* Check:

  * `llama-server` is running and reachable
  * The GUI is using the latest code on the intended branch
  * The local `config.yaml` points to the same host/port where `llama-server` is listening

---

### 4. Output continues as fake dialogue

If a simple prompt such as `Hey!` produces a long scripted conversation with extra `[You]` / `[Gemma]` turns, the app is likely using raw completion behavior without chat formatting.

Current server behavior:

* Prefer `/v1/chat/completions` with structured messages.
* If unavailable, fall back to `/completion` using Gemma turn markers:

  ```text
  <start_of_turn>user
  ...
  <end_of_turn>
  <start_of_turn>model
  ```

* In fallback mode, stop sequences are used to prevent the model from generating the next user turn.

Start a new chat after updating if an older session already contains runaway generated dialogue; old history can influence the next answer.

---

### 5. Output is too short

Short output can be normal if the model gives a concise answer, but check these settings:

* `n_predict`: maximum generated tokens. Increase it for longer answers.
* `server_endpoint`: keep it as `auto` so chat completions are preferred.

The app does not send fallback stop sequences to `/v1/chat/completions`; those stop sequences are only used for raw `/completion` fallback to prevent runaway dialogue.

---

### 6. Broken characters (e.g. `\ufffd`)

Handled internally by:

* unicode normalization
* unsupported char filtering

---

## 📌 Future Improvements (Optional)

* Streaming token output (real-time typing)
* Multi-model selection
* GPU offload tuning (Metal / Vulkan / OpenCL)
* Chat export (markdown / txt)

---

## OpenAI-Compatible Backend Settings

The app now uses an OpenAI-compatible Chat Completions backend by default. Start the GUI, then fill in the settings panel at the top of the main window:

* **Base URL**: your OpenAI-compatible `/v1` base URL, for example `http://127.0.0.1:8000/v1` or `http://localhost:1234/v1`
* **API Key**: optional for local servers; masked in the GUI and saved only in the local ignored settings file
* **Model Name**: the exact model ID exposed by your backend
* **Embedding Model**: optional model ID for `/v1/embeddings`; if blank, code can fall back to the chat model for embedding calls

Use **Save Settings** to persist those values to `openai_settings.json`. That file is ignored by git because it may contain secrets. Use **Test Connection** to check `/models` first; if model listing is unavailable, the app falls back to a minimal chat completion test when a model name is set.

The checked-in `config.example.yaml` contains non-secret defaults. Runtime connection values should be entered in the GUI or kept in your local, ignored `openai_settings.json`.

## Memory and RAG Foundation

Long chats no longer require every saved turn to be normalized and trimmed on each send. The GUI reads only `recent_message_limit` prior messages for the live prompt and can include a stored session summary as a compact memory block.

The RAG foundation is available for the next UI step:

* `OpenAICompatibleClient.embeddings(...)` calls `/v1/embeddings`
* `RagStore` saves chunk text, source metadata, and embedding vectors in SQLite
* cosine similarity search returns the top-k relevant chunks
* retrieved chunks can be formatted and passed into the prompt as memory context
