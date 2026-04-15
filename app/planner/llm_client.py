from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LLMClientError(Exception):
    """Raised when the OpenAI-compatible planner request fails."""


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    api_key: str = ""
    model: str = ""
    timeout: float = 120.0


class OpenAICompatibleLLMClient:
    """Small OpenAI-compatible chat-completions client for planning."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    def chat_completion(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.base_url.strip():
            raise LLMClientError("LLM_BASE_URL is required for /render_pptx planning.")
        if not self.settings.model.strip():
            raise LLMClientError("LLM_MODEL is required for /render_pptx planning.")

        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key.strip():
            headers["Authorization"] = f"Bearer {self.settings.api_key.strip()}"
        payload: dict[str, Any] = {
            "model": self.settings.model.strip(),
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        try:
            import requests  # type: ignore[import-not-found]
        except Exception as exc:
            raise LLMClientError("Planner HTTP calls require the requests package.") from exc

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.settings.timeout)
        except requests.RequestException as exc:
            raise LLMClientError(f"Planner request failed: {exc}") from exc

        if response.status_code >= 400:
            body = response.text.replace("\n", " ").strip()[:500]
            raise LLMClientError(f"HTTP {response.status_code} from planner endpoint: {body}")

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMClientError(f"Planner returned non-JSON response: {response.text[:500]}") from exc

        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("Planner response is missing choices.")
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMClientError("Planner response choice is malformed.")
        message = first.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        if isinstance(first.get("text"), str):
            return first["text"]
        raise LLMClientError("Planner response is missing assistant content.")
