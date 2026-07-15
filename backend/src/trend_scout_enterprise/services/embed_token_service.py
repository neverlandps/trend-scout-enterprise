"""Embed token service: generate, validate, revoke, and rotate read-only tokens."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from trend_scout_enterprise.core.security import hash_api_key, get_key_prefix
from trend_scout_enterprise.models.embed_token import EmbedToken
from trend_scout_enterprise.models.models import ApiKey, Workspace
from trend_scout_enterprise.services import workspace_service


EMBED_TOKEN_PREFIX = "tse_embed_"


def _generate_plaintext_token() -> str:
    return f"{EMBED_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def create_embed_token(
    db: Session,
    api_key: ApiKey,
    workspace_id: str,
    name: str = "SharePoint Web Part",
    ttl_days: int = 30,
) -> tuple[str, EmbedToken]:
    """Create a new embed token for a workspace. Admin role required."""
    workspace_service.require_admin(api_key)
    workspace = workspace_service.resolve_workspace(db, api_key, workspace_id)

    plaintext = _generate_plaintext_token()
    token = EmbedToken(
        id=uuid.uuid4().hex,
        workspace_id=workspace.id,
        name=name,
        token_hash=hash_api_key(plaintext),
        token_prefix=get_key_prefix(plaintext, length=8),
        scopes="read",
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
        created_by_api_key_id=api_key.id,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return plaintext, token


def verify_embed_token(
    db: Session,
    plaintext: str,
    workspace_id: str | None = None,
) -> EmbedToken:
    """Validate an embed token and update last_used_at. Returns token or raises HTTPException."""
    from fastapi import HTTPException, status

    token_hash = hash_api_key(plaintext)
    token = db.query(EmbedToken).filter(
        EmbedToken.token_hash == token_hash,
        EmbedToken.revoked_at.is_(None),
    ).first()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid embed token",
        )

    if token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Embed token expired",
        )

    if workspace_id and token.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Embed token not authorized for this workspace",
        )

    token.last_used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(token)
    return token


def list_embed_tokens(
    db: Session,
    api_key: ApiKey,
    workspace_id: str,
) -> List[EmbedToken]:
    """List embed tokens for a workspace. Admin role required."""
    workspace_service.require_admin(api_key)
    workspace = workspace_service.resolve_workspace(db, api_key, workspace_id)
    return db.query(EmbedToken).filter(
        EmbedToken.workspace_id == workspace.id,
    ).order_by(EmbedToken.created_at.desc()).all()


def revoke_embed_token(
    db: Session,
    api_key: ApiKey,
    workspace_id: str,
    token_id: str,
) -> EmbedToken:
    """Revoke an embed token. Admin role required."""
    workspace_service.require_admin(api_key)
    workspace = workspace_service.resolve_workspace(db, api_key, workspace_id)
    token = db.query(EmbedToken).filter(
        EmbedToken.id == token_id,
        EmbedToken.workspace_id == workspace.id,
    ).first()
    if not token:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Embed token not found",
        )
    token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(token)
    return token


def rotate_embed_token(
    db: Session,
    api_key: ApiKey,
    workspace_id: str,
    token_id: str,
    name: str | None = None,
    ttl_days: int = 30,
) -> tuple[str, EmbedToken]:
    """Revoke an existing embed token and create a replacement with the same name."""
    workspace_service.require_admin(api_key)
    workspace = workspace_service.resolve_workspace(db, api_key, workspace_id)
    old_token = db.query(EmbedToken).filter(
        EmbedToken.id == token_id,
        EmbedToken.workspace_id == workspace.id,
    ).first()
    if not old_token:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Embed token not found",
        )
    old_token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return create_embed_token(
        db,
        api_key,
        workspace.id,
        name or old_token.name,
        ttl_days=ttl_days,
    )
