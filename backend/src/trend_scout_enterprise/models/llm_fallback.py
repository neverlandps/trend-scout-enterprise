"""LLM fallback registry and health tracking."""

from sqlalchemy import Column, String, DateTime, Float, Boolean, Integer, Text, ForeignKey, Index
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class LlmFallbackProvider(Base):
    """Ordered fallback LLM providers used when the primary LLM fails."""

    __tablename__ = "llm_fallback_providers"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    base_url = Column(Text, nullable=False)
    api_key_encrypted = Column(Text)
    model = Column(String(255), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    priority = Column(Integer, default=0, nullable=False)  # lower = tried first
    is_enabled = Column(Boolean, default=True)
    timeout_seconds = Column(Integer, default=60)
    max_retries = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_llm_fallback_priority", "workspace_id", "priority"),)


class LlmHealthLog(Base):
    """Recent health/availability samples per LLM provider for fast fallback decisions."""

    __tablename__ = "llm_health_logs"

    id = Column(String(36), primary_key=True)
    provider_id = Column(String(36), ForeignKey("llm_providers.id"), nullable=True)
    fallback_provider_id = Column(String(36), ForeignKey("llm_fallback_providers.id"), nullable=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    status = Column(String(20), default="unknown")  # healthy, degraded, failed
    latency_ms = Column(Integer)
    error_message = Column(Text)
    recorded_at = Column(DateTime, server_default=func.now())
