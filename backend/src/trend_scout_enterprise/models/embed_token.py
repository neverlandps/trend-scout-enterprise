"""Embed token model for secure, read-only SharePoint web part access."""

from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class EmbedToken(Base):
    """Short-lived, read-only token used by SPFx web parts and embedded widgets."""

    __tablename__ = "embed_tokens"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(255), nullable=False, default="Embed")
    token_hash = Column(String(255), nullable=False, unique=True)
    token_prefix = Column(String(16), nullable=False)
    scopes = Column(Text, nullable=False, default="read")
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
    last_used_at = Column(DateTime)
    created_by_api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace")
    creator = relationship("ApiKey")

    __table_args__ = (
        Index("ix_embed_tokens_workspace_id", "workspace_id"),
        Index("ix_embed_tokens_token_prefix", "token_prefix"),
        Index("ix_embed_tokens_expires_at", "expires_at"),
    )
