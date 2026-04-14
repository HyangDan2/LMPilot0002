from __future__ import annotations

import re

from .token_handler import normalize_prompt_text


DEFAULT_SESSION_TITLE = "New Chat"
TITLE_WORD_RE = re.compile(r"[A-Za-z0-9가-힣][A-Za-z0-9가-힣'_-]*")


def derive_session_title(text: str, max_words: int = 8, max_chars: int = 60) -> str:
    text = normalize_prompt_text(text)
    words = TITLE_WORD_RE.findall(text)
    title = " ".join(words[:max_words]).strip()
    if not title:
        return DEFAULT_SESSION_TITLE
    if len(title) > max_chars:
        title = title[:max_chars].rstrip()
    return title or DEFAULT_SESSION_TITLE
