from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_RESPONSE_TOKEN_RESERVE = 256
DEFAULT_MAX_PROMPT_CHARS = 12000
OBJECT_REPLACEMENT_CHAR = "\ufffc"
GEMMA_ASSISTANT_CUE = "<start_of_turn>model"
GEMMA_END_OF_TURN = "<end_of_turn>"


@dataclass(frozen=True)
class ModelPrompt:
    messages: list[dict[str, str]]
    completion_prompt: str
    was_limited: bool = False


def estimate_token_count(text: str) -> int:
    """Estimate token usage with a conservative whitespace-based approximation."""
    return len(text.split())


def truncate_text_to_token_budget(text: str, max_tokens: int) -> str:
    """Trim text to the configured approximate token budget while keeping lines."""
    if max_tokens <= 0:
        return ""

    remaining = max_tokens
    kept_lines: list[str] = []

    for line in text.splitlines():
        words = line.split()
        if not words:
            kept_lines.append("")
            continue

        if len(words) <= remaining:
            kept_lines.append(line)
            remaining -= len(words)
            continue

        if remaining > 0:
            leading_space_count = len(line) - len(line.lstrip())
            kept_lines.append((" " * leading_space_count) + " ".join(words[:remaining]))
        break

    return "\n".join(kept_lines).rstrip()


def normalize_prompt_text(text: str, *, max_blank_lines: int = 1) -> str:
    """Prepare pasted GUI text while preserving useful multiline structure."""
    if not isinstance(text, str):
        text = str(text)

    text = text.replace(OBJECT_REPLACEMENT_CHAR, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [line.rstrip() for line in text.split("\n")]
    normalized_lines: list[str] = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= max_blank_lines:
                normalized_lines.append("")
            continue

        blank_count = 0
        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip()


def truncate_text_to_char_budget(text: str, max_chars: int = DEFAULT_MAX_PROMPT_CHARS) -> str:
    """Trim very long input, including no-space text that word counts cannot reduce."""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def handle_token_limits(conversation: list[str], max_tokens: int) -> list[str]:
    """Return the newest conversation turns that fit the approximate token budget."""
    if max_tokens <= 0:
        return []

    selected: list[str] = []
    total_tokens = 0

    for turn in reversed(conversation):
        turn_tokens = estimate_token_count(turn)
        remaining_tokens = max_tokens - total_tokens
        if remaining_tokens <= 0:
            break

        if turn_tokens <= remaining_tokens:
            selected.append(turn)
            total_tokens += turn_tokens
        else:
            selected.append(truncate_text_to_token_budget(turn, remaining_tokens))
            break

    selected.reverse()
    return [turn for turn in selected if turn]


def _canonical_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized in {"assistant", "model", "gemma"}:
        return "assistant"
    if normalized == "system":
        return "system"
    return "user"


def _text_fits_budget(text: str, max_tokens: int, max_chars: int) -> bool:
    return estimate_token_count(text) <= max_tokens and len(text) <= max_chars


def format_chat_message(role: str, content: str) -> dict[str, str] | None:
    normalized_content = normalize_prompt_text(content)
    if not normalized_content:
        return None
    return {"role": _canonical_role(role), "content": normalized_content}


def _completion_turn_for_message(message: dict[str, str]) -> str:
    role = message["role"]
    content = message["content"]
    if role == "system":
        return f"System instruction:\n{content}"
    if role == "assistant":
        gemma_role = "model"
    else:
        gemma_role = "user"
    return f"<start_of_turn>{gemma_role}\n{content}{GEMMA_END_OF_TURN}"


def format_gemma_completion_prompt(messages: list[dict[str, str]]) -> str:
    turns = [_completion_turn_for_message(message) for message in messages if message.get("content")]
    turns.append(GEMMA_ASSISTANT_CUE)
    return "\n".join(turns)


def _messages_fit_budget(messages: list[dict[str, str]], max_tokens: int, max_chars: int) -> bool:
    return _text_fits_budget(format_gemma_completion_prompt(messages), max_tokens, max_chars)


def _truncate_message_to_budget(
    message: dict[str, str],
    fixed_messages: list[dict[str, str]],
    max_tokens: int,
    max_chars: int,
) -> dict[str, str] | None:
    empty_message = {"role": message["role"], "content": ""}
    base_turns = [
        _completion_turn_for_message(fixed_message)
        for fixed_message in fixed_messages
        if fixed_message.get("content")
    ]
    base_turns.extend([_completion_turn_for_message(empty_message), GEMMA_ASSISTANT_CUE])
    base_prompt = "\n".join(base_turns)
    remaining_chars = max_chars - len(base_prompt)
    remaining_tokens = max_tokens - estimate_token_count(base_prompt)
    if remaining_chars <= 0 or remaining_tokens <= 0:
        return None

    content = truncate_text_to_char_budget(message["content"], remaining_chars)
    content = truncate_text_to_token_budget(content, remaining_tokens)
    if not content:
        return None
    return {"role": message["role"], "content": content}


def trim_messages_to_budget(
    messages: list[dict[str, str]],
    max_tokens: int,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> list[dict[str, str]]:
    """Keep the newest chat messages that fit the Gemma completion fallback budget."""
    if max_tokens <= 0 or max_chars <= 0:
        return []

    fixed_messages = [message for message in messages if message["role"] == "system"]
    conversation_messages = [message for message in messages if message["role"] != "system"]
    selected: list[dict[str, str]] = []

    for message in reversed(conversation_messages):
        candidate = fixed_messages + [message] + selected
        if _messages_fit_budget(candidate, max_tokens, max_chars):
            selected.insert(0, message)
            continue

        if selected:
            break

        truncated = _truncate_message_to_budget(message, fixed_messages, max_tokens, max_chars)
        if truncated is not None:
            selected.insert(0, truncated)
        break

    if fixed_messages and conversation_messages and not selected:
        return trim_messages_to_budget(conversation_messages, max_tokens, max_chars)

    result = fixed_messages + selected
    if fixed_messages and not _messages_fit_budget(result, max_tokens, max_chars):
        return selected
    return result


def build_model_prompt_request(
    messages: list[dict[str, Any]],
    current_user_text: str,
    max_tokens: int,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    system_prompt: str | None = None,
    memory_context: str | None = None,
) -> ModelPrompt:
    """Build structured chat messages and a Gemma-template completion fallback."""
    chat_messages: list[dict[str, str]] = []

    system_message = format_chat_message("system", system_prompt or "")
    if system_message is not None:
        chat_messages.append(system_message)

    memory_message = format_chat_message("system", memory_context or "")
    if memory_message is not None:
        chat_messages.append(memory_message)

    for message in messages:
        formatted_message = format_chat_message(
            str(message.get("role", "")),
            str(message.get("content", "")),
        )
        if formatted_message is not None:
            chat_messages.append(formatted_message)

    current_message = format_chat_message("user", current_user_text)
    if current_message is not None:
        chat_messages.append(current_message)

    trimmed_messages = trim_messages_to_budget(chat_messages, max_tokens, max_chars)
    return ModelPrompt(
        messages=trimmed_messages,
        completion_prompt=format_gemma_completion_prompt(trimmed_messages),
        was_limited=trimmed_messages != chat_messages,
    )


def build_model_prompt(
    messages: list[dict[str, Any]],
    current_user_text: str,
    max_tokens: int,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    system_prompt: str | None = None,
    memory_context: str | None = None,
) -> str:
    """Build the final history-aware prompt sent to the model."""
    return build_model_prompt_request(
        messages,
        current_user_text,
        max_tokens,
        max_chars,
        system_prompt,
        memory_context,
    ).completion_prompt


def build_memory_context(
    summary: str = "",
    retrieved_context: str = "",
    max_chars: int = 4000,
) -> str:
    parts: list[str] = []
    normalized_summary = normalize_prompt_text(summary)
    normalized_retrieval = normalize_prompt_text(retrieved_context)

    if normalized_summary:
        parts.append(f"Conversation summary:\n{normalized_summary}")
    if normalized_retrieval:
        parts.append(f"Relevant retrieved context:\n{normalized_retrieval}")

    if not parts:
        return ""
    return truncate_text_to_char_budget("\n\n".join(parts), max_chars)


def prompt_token_budget(ctx_size: int, reserve: int = DEFAULT_RESPONSE_TOKEN_RESERVE) -> int:
    """Leave space in the context window for the model response."""
    return max(1, ctx_size - reserve)
