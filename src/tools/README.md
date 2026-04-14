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

For future tools, add a module with the implementation, register a new dictionary entry in `TOOL_REGISTRY`, and keep the handler signature as:

```python
def handler(arguments: dict[str, object]) -> str:
    ...
```

Do not run arbitrary code from tool arguments. Validate inputs before calling external services or the filesystem.
