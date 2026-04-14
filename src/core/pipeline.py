from __future__ import annotations

from typing import Any

from .providers import BaseLLMProvider
from .schemas import ModelAction, parse_structured_output
from .state import RunState
from .tools import ToolRegistry


def prepare_messages(state: RunState) -> RunState:
    state.add_log("prepare_messages")
    if state.system_prompt and not any(message.get("role") == "system" for message in state.messages):
        state.messages.insert(0, {"role": "system", "content": state.system_prompt})
    if not state.messages and state.user_input.strip():
        state.messages.append({"role": "user", "content": state.user_input})
    return state


def call_model(state: RunState, provider: BaseLLMProvider) -> RunState:
    state.add_log(f"call_model:{provider.name}:{provider.model_name}")
    if not state.messages:
        state.set_error("No messages available for model call.")
        return state
    try:
        raw_output = provider.generate(state.messages)
    except Exception as exc:
        state.set_error(str(exc))
        return state
    state.metadata["raw_model_output"] = raw_output
    return state


def parse_response(state: RunState) -> RunState:
    state.add_log("parse_response")
    raw_output = str(state.metadata.get("raw_model_output", ""))
    if not raw_output:
        state.add_log("parse_response:no output to parse")
        return state
    parsed_output, error = parse_structured_output(raw_output)
    if error is not None:
        state.metadata["structured_parse_error"] = error
        state.add_log(f"parse_response:structured output unavailable: {error}")
        return state
    state.parsed_output = parsed_output
    state.add_log(f"parse_response:action={parsed_output.action}")
    return state


def execute_tools(state: RunState, registry: ToolRegistry) -> RunState:
    state.add_log("execute_tools")
    parsed_output = state.parsed_output
    if not isinstance(parsed_output, ModelAction) or parsed_output.action != "tool":
        return state
    tool_name = parsed_output.tool_name or ""
    if not tool_name:
        state.add_log("execute_tools:tool action missing tool_name")
        return state
    if not state.metadata.get("execute_model_tools", False):
        state.add_log(f"execute_tools:model-requested tool '{tool_name}' was not auto-executed")
        return state
    if not registry.has(tool_name):
        state.set_error(f"Unknown tool requested by model: {tool_name}")
        return state
    try:
        state.tool_results[tool_name] = registry.execute(tool_name, parsed_output.tool_input)
    except Exception as exc:
        state.set_error(f"Tool {tool_name} failed: {exc}")
    return state


def finalize_answer(state: RunState) -> RunState:
    state.add_log("finalize_answer")
    parsed_output = state.parsed_output
    if isinstance(parsed_output, ModelAction) and parsed_output.answer.strip():
        state.final_answer = parsed_output.answer.strip()
        return state
    state.final_answer = str(state.metadata.get("raw_model_output", "")).strip()
    return state


def run_pipeline(state: RunState, provider: BaseLLMProvider, registry: ToolRegistry) -> RunState:
    state.provider_name = provider.name
    state.model_name = provider.model_name
    state = prepare_messages(state)
    if state.error:
        return state
    state = call_model(state, provider)
    if state.error:
        return state
    state = parse_response(state)
    if state.error:
        return state
    state = execute_tools(state, registry)
    if state.error:
        return state
    state = finalize_answer(state)
    return state
