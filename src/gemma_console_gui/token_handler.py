from __future__ import annotations


DEFAULT_RESPONSE_TOKEN_RESERVE = 256


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


def prompt_token_budget(ctx_size: int, reserve: int = DEFAULT_RESPONSE_TOKEN_RESERVE) -> int:
    """Leave space in the context window for the model response."""
    return max(1, ctx_size - reserve)
