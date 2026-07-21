"""Pydantic schemas for LLM fallback provider management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LlmFallbackProviderBase(BaseModel):
    """Common fields for fallback provider schemas."""

    name: str = Field(..., max_length=255)
    base_url: str
    api_key: str | None = None  # plain on input, encrypted on storage
    model: str = Field(..., max_length=255)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    priority: int = Field(default=0, ge=0)
    is_enabled: bool = True
    timeout_seconds: int = Field(default=60, ge=1)
    max_retries: int = Field(default=1, ge=0)


class LlmFallbackProviderCreate(LlmFallbackProviderBase):
    """Request schema for creating a fallback LLM provider."""


class LlmFallbackProviderUpdate(BaseModel):
    """Request schema for updating a fallback provider (all fields optional)."""

    name: str | None = Field(default=None, max_length=255)
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = Field(default=None, max_length=255)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_retries: int | None = Field(default=None, ge=0)
    priority: int | None = Field(default=None, ge=0)
    is_enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1)


class LlmFallbackProviderOut(LlmFallbackProviderBase):
    """Response schema for a fallback LLM provider."""

    id: str
    api_key: str | None = None  # masked in responses
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LlmFallbackHealthCheckRequest(BaseModel):
    """Request schema for health-checking a fallback provider."""

    provider_id: str


class LlmFallbackHealthOut(BaseModel):
    """Response schema for a fallback provider health check."""

    provider_id: str
    name: str
    status: str
    latency_ms: int | None = None
    error_message: str | None = None


class LlmFallbackStrategyOut(BaseModel):
    """Response schema describing the active fallback strategy."""

    primary: dict[str, Any]
    fallbacks: list[LlmFallbackProviderOut]
    fallback_enabled: bool = True
    last_failover_at: datetime | None = None
