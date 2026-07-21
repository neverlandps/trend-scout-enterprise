"""LLM service with retry, fallback provider chain, and health tracking."""

import json
from typing import Any

import httpx
import structlog

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.encryption import decrypt_value, encrypt_value
from trend_scout_enterprise.models.llm_fallback import LlmFallbackProvider, LlmHealthLog
from trend_scout_enterprise.models.models import LlmProvider


logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT = 60.0


class LlmProviderConfig:
    """Value object describing a single LLM provider endpoint."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def to_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def to_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


class LlmService:
    """Client for user-managed OpenAI-compatible LLM endpoints with fallback chain."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        fallback_providers: list[LlmProviderConfig] | None = None,
    ) -> None:
        """Initialize LLM client with primary provider and optional fallback chain."""
        self.base_url = (base_url or settings.llm_default_base_url).rstrip("/")
        self.api_key = api_key
        self.model = model or settings.llm_default_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.fallback_providers = fallback_providers or []

    def _primary_provider(self) -> LlmProviderConfig:
        return LlmProviderConfig(
            name="primary",
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=DEFAULT_TIMEOUT,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request, falling back to configured providers on failure."""
        providers = [self._primary_provider()] + list(self.fallback_providers)
        last_error: Exception | None = None

        for provider in providers:
            try:
                payload = provider.to_payload(messages)
                if temperature is not None:
                    payload["temperature"] = temperature
                if max_tokens is not None:
                    payload["max_tokens"] = max_tokens
                async with httpx.AsyncClient(timeout=provider.timeout) as client:
                    response = await client.post(
                        f"{provider.base_url}/chat/completions",
                        headers=provider.to_headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        raise last_error or RuntimeError("All LLM providers failed")

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


class LlmFallbackRegistry:
    """Manage ordered fallback LLM providers and health logging."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def _mask_api_key(self, encrypted: str | None) -> str | None:
        return None

    def list_providers(
        self,
        workspace_id: str | None = None,
    ) -> list[LlmFallbackProvider]:
        query = self.db.query(LlmFallbackProvider).filter(
            LlmFallbackProvider.is_enabled == True
        )
        if workspace_id is not None:
            query = query.filter(
                (LlmFallbackProvider.workspace_id == workspace_id)
                | (LlmFallbackProvider.workspace_id.is_(None))
            )
        return query.order_by(LlmFallbackProvider.priority.asc()).all()

    def create_provider(
        self,
        payload: Any,
        workspace_id: str | None = None,
    ) -> LlmFallbackProvider:
        import uuid

        provider = LlmFallbackProvider(
            id=uuid.uuid4().hex,
            workspace_id=workspace_id,
            name=payload.name,
            base_url=payload.base_url,
            api_key_encrypted=encrypt_value(payload.api_key) if payload.api_key else None,
            model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            priority=payload.priority,
            is_enabled=payload.is_enabled,
            timeout_seconds=payload.timeout_seconds,
            max_retries=payload.max_retries,
        )
        self.db.add(provider)
        self.db.commit()
        self.db.refresh(provider)
        return provider

    def get_provider(self, provider_id: str) -> LlmFallbackProvider | None:
        return self.db.query(LlmFallbackProvider).filter(
            LlmFallbackProvider.id == provider_id
        ).first()

    def update_provider(
        self,
        provider: LlmFallbackProvider,
        payload: Any,
    ) -> LlmFallbackProvider:
        update_data = payload.model_dump(exclude_unset=True)
        if "api_key" in update_data:
            new_key = update_data.pop("api_key")
            if new_key:
                provider.api_key_encrypted = encrypt_value(new_key)
        for field, value in update_data.items():
            setattr(provider, field, value)
        self.db.commit()
        self.db.refresh(provider)
        return provider

    def delete_provider(self, provider: LlmFallbackProvider) -> None:
        self.db.delete(provider)
        self.db.commit()

    def to_service_providers(self, workspace_id: str | None = None) -> list[LlmProviderConfig]:
        """Convert configured fallback providers to LlmProviderConfig objects."""
        providers = []
        for p in self.list_providers(workspace_id=workspace_id):
            api_key = None
            if p.api_key_encrypted:
                api_key = decrypt_value(p.api_key_encrypted)
            providers.append(
                LlmProviderConfig(
                    name=p.name,
                    base_url=p.base_url,
                    api_key=api_key,
                    model=p.model,
                    temperature=p.temperature,
                    max_tokens=p.max_tokens,
                    timeout=float(p.timeout_seconds),
                )
            )
        return providers

    def log_health(
        self,
        provider_id: str | None,
        fallback_provider_id: str | None,
        workspace_id: str | None,
        status: str,
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> LlmHealthLog:
        import uuid

        log = LlmHealthLog(
            id=uuid.uuid4().hex,
            provider_id=provider_id,
            fallback_provider_id=fallback_provider_id,
            workspace_id=workspace_id,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log


def build_llm_service_with_fallback(
    db: Any,
    workspace_id: str | None = None,
) -> LlmService:
    """Build an LlmService using the default provider plus configured fallback chain."""
    primary = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    registry = LlmFallbackRegistry(db)
    fallback_configs = registry.to_service_providers(workspace_id=workspace_id)

    if primary:
        primary_key = None
        if primary.api_key_encrypted:
            primary_key = decrypt_value(primary.api_key_encrypted)
        return LlmService(
            base_url=primary.base_url,
            api_key=primary_key,
            model=primary.model,
            temperature=primary.temperature,
            max_tokens=primary.max_tokens,
            fallback_providers=fallback_configs,
        )
    return LlmService(fallback_providers=fallback_configs)


def get_default_llm_service_or_none(db: Any) -> LlmService | None:
    """Build the default LlmService, returning None if configuration fails."""
    try:
        return build_llm_service_with_fallback(db)
    except Exception as exc:
        logger.warning("llm_service_unavailable", error=str(exc))
        return None
