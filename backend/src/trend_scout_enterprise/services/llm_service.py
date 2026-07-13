"""LLM service for OpenAI-compatible API calls."""

import json
from typing import Any

import httpx

from trend_scout_enterprise.core.config import settings


DEFAULT_TIMEOUT = 60.0


class LlmService:
    """Client for user-managed OpenAI-compatible LLM endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize LLM client with provider settings."""
        self.base_url = (base_url or settings.llm_default_base_url).rstrip("/")
        self.api_key = api_key
        self.model = model or settings.llm_default_model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request to the LLM endpoint."""
        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def summarize_text(self, text: str, max_tokens: int = 512) -> str:
        """Summarize a block of text using the LLM."""
        messages = [
            {
                "role": "system",
                "content": "You are a concise summarizer. Summarize the following text in 2-3 sentences.",
            },
            {"role": "user", "content": text},
        ]
        result = await self.chat_completion(messages, max_tokens=max_tokens)
        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return ""

    def _parse_score_response(self, content: str, dimensions: list[str]) -> dict[str, float]:
        """Parse LLM score response, returning zeroes for missing dimensions."""
        # Try to extract JSON if wrapped in markdown fences
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:-1]).strip()
        try:
            scores = json.loads(cleaned)
            return {
                d: min(1.0, max(0.0, float(scores.get(d, 0.0))))
                for d in dimensions
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            return {d: 0.0 for d in dimensions}

    async def score_dimensions(self, text: str, dimensions: list[str]) -> dict[str, float]:
        """Score text across multiple dimensions using the LLM."""
        dim_str = ", ".join(dimensions)
        messages = [
            {
                "role": "system",
                "content": (
                    f"Score the following text on these dimensions ({dim_str}) "
                    "from 0.0 to 1.0. Return ONLY a JSON object with dimension names as keys and scores as values."
                ),
            },
            {"role": "user", "content": text},
        ]
        result = await self.chat_completion(messages, max_tokens=512)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return self._parse_score_response(content, dimensions)
