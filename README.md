# Gemma Console GUI (PySide6 MVP)

A lightweight OOP-based PySide6 desktop GUI for interacting with a persistent `llama-cli` session.

Designed for Raspberry Pi / Linux environments with stability-focused output handling.

---

## ✨ Features

* 🖥️ PySide6 desktop GUI (clean chat interface)
* 🔁 Persistent background `llama-cli` session (via `pexpect`, no subprocess per request)
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

---

## 🧠 Behavior Changes (Important)

* ❌ **No auto session creation on startup**

  * User must manually click **"New Chat"**
* 🧭 Startup message:

  ```
  Select a session or click New Chat.
  ```

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
python run.py --config config.yaml
```

---

## ⚙️ Default Paths

* **llama-cli**

  ```
  /home/pi/Downloads/llama.cpp/build/bin/llama-cli
  ```

* **Model (GGUF)**

  ```
  /home/pi/.cache/huggingface/hub/models--ggml-org--gemma-3-1b-it-GGUF/snapshots/f9c28bcd85737ffc5aef028638d3341d49869c27/gemma-3-1b-it-Q4_K_M.gguf
  ```

👉 Modify paths in:

```yaml
config.yaml
```

---

## 🧩 Architecture Overview

```
GUI (PySide6)
   │
   ├── QThread (ChatWorker)
   │       │
   │       └── LlamaConsoleSession (pexpect)
   │
   ├── SQLite (ChatRepository)
   │
   └── Text Processing
          ├── ANSI strip
          ├── Unicode normalize
          └── Glyph filtering
```

---

## ⚠️ Notes (Raspberry Pi)

* Emoji may break rendering → filtered by design
* Ensure `llama-cli` runs independently before GUI
* If output looks corrupted:

  * Check locale (`UTF-8`)
  * Verify terminal encoding

---

## 🔧 Troubleshooting

### 1. Model not loading

* Check `config.yaml` paths
* Verify `.gguf` file exists

---

### 2. llama-cli error

```bash
ldd llama-cli
```

→ missing `.so` needs to be resolved

---

### 3. No response / stuck

* Check:

  * `pexpect` installed
  * llama-cli works manually

---

### 4. Broken characters (e.g. `\ufffd`)

Handled internally by:

* unicode normalization
* unsupported char filtering

---

## 📌 Future Improvements (Optional)

* Streaming token output (real-time typing)
* Multi-model selection
* GPU offload tuning (Metal / Vulkan / OpenCL)
* Chat export (markdown / txt)
