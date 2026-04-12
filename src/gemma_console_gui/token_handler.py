from __future__ import annotations


DEFAULT_RESPONSE_TOKEN_RESERVE = 256
DEFAULT_MAX_PROMPT_CHARS = 12000
OBJECT_REPLACEMENT_CHAR = "\ufffc"


def estimate_token_count(text: str) -> int:
    """Estimate token usage with a conservative whitespace-based approximation."""
    return len(text.split())


def truncate_text_to_token_budget(text: str, max_tokens: int) -> str:
    """Trim text to the configured approximate token budget."""
    if max_tokens <= 0:
        return ""

    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens])


def normalize_prompt_text(text: str) -> str:
    """Prepare pasted GUI text for one-line console submission."""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace(OBJECT_REPLACEMENT_CHAR, " ")
    return " ".join(text.split())


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


def limit_prompt_text(
    text: str,
    max_tokens: int,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> str:
    """Apply both approximate token and character limits to a prompt."""
    normalized = normalize_prompt_text(text)
    char_limited = truncate_text_to_char_budget(normalized, max_chars)
    limited_turns = handle_token_limits([char_limited], max_tokens)
    return limited_turns[0] if limited_turns else ""


def prompt_token_budget(ctx_size: int, reserve: int = DEFAULT_RESPONSE_TOKEN_RESERVE) -> int:
    """Leave space in the context window for the model response."""
    return max(1, ctx_size - reserve)
