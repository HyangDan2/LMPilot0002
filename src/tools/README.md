# Local Tools

Tools live in this package so the GUI and future model-driven tool calls can use the same registry.

Each tool is registered in `registry.py` as a dictionary with:

- `name`
- `description`
- `parameters`
- `schema`
- `handler`

The current calculator is available manually from chat:

```text
/calc 2 + 3 * 4
/calculator (2 + 3) * 4
```

Attached files are available through the prompt-transforming tool command:

```text
/use_file example.txt summarize this file
```

`/use_file` reads one file from the reusable attachment list selected in the GUI, builds file context, and then sends the transformed prompt to the normal LLM flow. The first argument is the attached filename or full path. Everything after that is the model instruction:

```text
/use_file example.txt translate file to Japanese
```

Image analysis uses the same pattern but sends OpenAI-compatible vision content:

```text
/analyze_image chart.png summarize the visible trend
```

`/analyze_image` sends one attached image as a base64 data URL plus the instruction text. Use an OpenAI-compatible or chat-completions vision backend for this command.

For future tools, add a module with the implementation, register a new dictionary entry in `TOOL_REGISTRY`, and keep the handler signature as:

```python
def handler(arguments: dict[str, object]) -> object:
    ...
```

Do not run arbitrary code from tool arguments. Validate inputs before calling external services or the filesystem.
