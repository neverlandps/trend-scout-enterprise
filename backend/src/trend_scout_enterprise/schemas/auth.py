"""Pydantic schemas for authentication."""

from pydantic import BaseModel, ConfigDict, Field


class MicrosoftAuthConfigIn(BaseModel):
    """Request schema for configuring Microsoft Entra ID."""

    tenant_id: str = Field(..., max_length=255)
    client_id: str = Field(..., max_length=255)
    client_secret: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., max_length=500)
    is_enabled: bool = True


class MicrosoftAuthConfigOut(BaseModel):
    """Response schema for Microsoft Entra ID configuration (secret hidden)."""

    id: str
    name: str
    tenant_id: str
    client_id: str
    redirect_uri: str
    is_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class UserInfo(BaseModel):
    """Basic user profile returned after login."""

    id: str
    email: str
    name: str | None = None


class LoginResponse(BaseModel):
    """Response schema for successful OAuth2 login."""

    access_token: str
    token_type: str
    expires_in: int
    user: UserInfo
