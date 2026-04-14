# Architecture Notes

This project stays lightweight and does not use LangChain or LangGraph. The core flow is explicit Python functions and small classes.

## RunState

`src/core/state.py` defines `RunState`, the shared state object for one model execution. It carries:

- raw user input
- provider and model names
- system prompt
- chat messages
- tool results
- parsed structured output
- final answer
- error text
- step logs
- metadata for raw model output and debug details

Use `state.add_log(...)` for trace entries and `state.set_error(...)` for hard failures.

## Pipeline Steps

`src/core/pipeline.py` keeps the flow in plain node-style functions:

- `prepare_messages(state)`
- `call_model(state, provider)`
- `parse_response(state)`
- `execute_tools(state, registry)`
- `finalize_answer(state)`
- `run_pipeline(state, provider, registry)`

The orchestrator is intentionally simple. It runs each step in order and stops when `state.error` is set.

## Tools

`src/core/tools.py` defines `ToolSpec` and `ToolRegistry`. The registry supports:

- `register(tool)`
- `get(name)`
- `has(name)`
- `list_tools()`
- `execute(name, arguments)`
- provider-facing schema export

`build_default_tool_registry()` adapts the existing `src/tools/registry.py` tools, so calculator, `/use_file`, and `/image_analyze` stay in one place.

Tool execution remains explicit. The pipeline does not run model-requested tools unless `state.metadata["execute_model_tools"]` is set to `True`.

## Structured Output

`src/core/schemas.py` defines a structured model response with Pydantic when available:

```json
{
  "action": "answer",
  "tool_name": null,
  "tool_input": {},
  "answer": "Final text"
}
```

`parse_structured_output(...)` tries to parse JSON, validates it, and returns a structured object. If the model returns normal plain text, parsing fails gracefully, the raw answer is preserved, and the parse error is stored in `RunState.metadata["structured_parse_error"]`.

## Providers

`src/core/providers.py` defines `BaseLLMProvider` and `OpenAICompatibleProvider`.

The provider interface is:

```python
generate(messages, **kwargs) -> str
```

`OpenAICompatibleSession.ask(...)` now wraps the existing `OpenAICompatibleClient` with `OpenAICompatibleProvider` and sends it through `run_pipeline(...)`. Streaming behavior remains unchanged; if streaming falls back to non-streaming, the pipeline is used there too.
