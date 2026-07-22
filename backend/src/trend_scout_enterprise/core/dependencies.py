"""Shared FastAPI dependencies."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import lookup_api_key_by_plaintext
from trend_scout_enterprise.models.embed_token import EmbedToken
from trend_scout_enterprise.models.models import ApiKey, Workspace
from trend_scout_enterprise.services import workspace_service
from trend_scout_enterprise.services.embed_token_service import verify_embed_token


async def get_current_api_key(
    x_api_key: str | None = Header(None, alias=settings.api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Resolve the API key to an ApiKey entity."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    api_key = lookup_api_key_by_plaintext(db, x_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    api_key.last_used_at = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(api_key)
    return api_key


async def get_current_workspace(
    x_workspace_id: str | None = Header(None, alias=settings.workspace_id_header),
    x_api_key: str | None = Header(None, alias=settings.api_key_header),
    db: Session = Depends(get_db),
) -> Workspace:
    """Resolve the authenticated API key and its requested/default workspace."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    api_key = lookup_api_key_by_plaintext(db, x_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    api_key.last_used_at = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(api_key)
    return workspace_service.resolve_workspace(db, api_key, x_workspace_id)

async def get_current_workspace_unified(
    x_workspace_id: str | None = Header(None, alias=settings.workspace_id_header),
    x_api_key: str | None = Header(None, alias=settings.api_key_header),
    x_embed_token: str | None = Header(None, alias="X-Embed-Token"),
    db: Session = Depends(get_db),
) -> Workspace:
    """Resolve workspace from either API key or embed token.

    Embed tokens are read-only and intended for embedded widgets such as
    SharePoint web parts. They do not grant write access.
    """
    if x_api_key:
        return await get_current_workspace(x_workspace_id, x_api_key, db)

    if x_embed_token:
        token = verify_embed_token(db, x_embed_token, x_workspace_id)
        if x_workspace_id and token.workspace_id != x_workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Embed token not authorized for this workspace",
            )
        return token.workspace

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing API key or embed token",
    )


async def get_current_embed_token(
    x_embed_token: str | None = Header(None, alias="X-Embed-Token"),
    x_workspace_id: str | None = Header(None, alias=settings.workspace_id_header),
    db: Session = Depends(get_db),
) -> EmbedToken:
    """Resolve the X-Embed-Token header to an active EmbedToken entity.

    Embed tokens are read-only, short-lived tokens intended for SharePoint web parts
    and embedded widgets. They are not API keys and do not grant write access.
    """
    if not x_embed_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing embed token",
        )
    token = verify_embed_token(db, x_embed_token, x_workspace_id)
    return token


def require_embed_token_scope(scope: str):
    """Factory dependency that checks the embed token has the required scope."""
    async def _check_scope(token: EmbedToken = Depends(get_current_embed_token)) -> EmbedToken:
        if scope not in token.scopes.split(","):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Embed token missing required scope: {scope}",
            )
        return token
    return _check_scope


async def get_workspace_from_embed_token(
    token: EmbedToken = Depends(get_current_embed_token),
) -> Workspace:
    """Return the workspace associated with the embed token."""
    return token.workspace
