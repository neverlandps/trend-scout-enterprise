"""Pydantic schemas for embed token management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmbedTokenCreate(BaseModel):
    name: str = Field(default="SharePoint Web Part", min_length=1, max_length=255)
    ttl_days: int = Field(default=30, ge=1, le=365)


class EmbedTokenRotate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    ttl_days: int = Field(default=30, ge=1, le=365)


class EmbedTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    token_prefix: str
    scopes: str
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EmbedTokenWithPlaintext(BaseModel):
    token: str
    embed_token: EmbedTokenOut
