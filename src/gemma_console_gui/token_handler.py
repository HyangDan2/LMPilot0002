from __future__ import annotations

from typing import Any


DEFAULT_RESPONSE_TOKEN_RESERVE = 256
DEFAULT_MAX_PROMPT_CHARS = 12000
OBJECT_REPLACEMENT_CHAR = "\ufffc"
TURN_SEPARATOR = "\n\n"
ASSISTANT_PROMPT_CUE = "[Gemma]"

ROLE_LABELS = {
    "user": "You",
    "assistant": "Gemma",
    "system": "System",
}


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


def _join_turns(turns: list[str]) -> str:
    return TURN_SEPARATOR.join(turns)


def _text_fits_budget(text: str, max_tokens: int, max_chars: int) -> bool:
    return estimate_token_count(text) <= max_tokens and len(text) <= max_chars


def trim_turns_to_budget(
    turns: list[str],
    max_tokens: int,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> list[str]:
    """Keep the newest turns that fit the prompt budget."""
    if max_tokens <= 0 or max_chars <= 0:
        return []

    selected_newest_first: list[str] = []

    for turn in reversed([turn for turn in turns if turn]):
        candidate_newest_first = selected_newest_first + [turn]
        candidate = _join_turns(list(reversed(candidate_newest_first)))

        if _text_fits_budget(candidate, max_tokens, max_chars):
            selected_newest_first = candidate_newest_first
            continue

        if selected_newest_first:
            break

        truncated = truncate_text_to_char_budget(turn, max_chars)
        truncated = truncate_text_to_token_budget(truncated, max_tokens)
        if truncated:
            selected_newest_first = [truncated]
        break

    return list(reversed(selected_newest_first))


def format_prompt_turn(role: str, content: str) -> str:
    label = ROLE_LABELS.get(role, role.title())
    normalized_content = normalize_prompt_text(content)
    if not normalized_content:
        return ""
    return f"[{label}]\n{normalized_content}"


def build_model_prompt(
    messages: list[dict[str, Any]],
    current_user_text: str,
    max_tokens: int,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> str:
    """Build the final history-aware prompt sent to the model."""
    turns: list[str] = []

    for message in messages:
        role = str(message.get("role", ""))
        content = str(message.get("content", ""))
        formatted_turn = format_prompt_turn(role, content)
        if formatted_turn:
            turns.append(formatted_turn)

    current_turn = format_prompt_turn("user", current_user_text)
    if current_turn:
        turns.append(current_turn)

    cue_token_cost = estimate_token_count(ASSISTANT_PROMPT_CUE)
    cue_char_cost = len(TURN_SEPARATOR) + len(ASSISTANT_PROMPT_CUE)
    trimmed_turns = trim_turns_to_budget(
        turns,
        max_tokens=max_tokens - cue_token_cost,
        max_chars=max_chars - cue_char_cost,
    )
    if not trimmed_turns:
        return ASSISTANT_PROMPT_CUE

    return _join_turns(trimmed_turns + [ASSISTANT_PROMPT_CUE])


def prompt_token_budget(ctx_size: int, reserve: int = DEFAULT_RESPONSE_TOKEN_RESERVE) -> int:
    """Leave space in the context window for the model response."""
    return max(1, ctx_size - reserve)
