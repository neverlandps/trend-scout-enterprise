"""Embed token API endpoints for secure SharePoint / embedded widget access."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.models import ApiKey, Workspace
from trend_scout_enterprise.schemas.embed_token import (
    EmbedTokenCreate,
    EmbedTokenOut,
    EmbedTokenRotate,
    EmbedTokenWithPlaintext,
)
from trend_scout_enterprise.services import embed_token_service

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/embed-token",
    response_model=EmbedTokenWithPlaintext,
    status_code=status.HTTP_201_CREATED,
)
def create_embed_token(
    workspace_id: str,
    payload: EmbedTokenCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> EmbedTokenWithPlaintext:
    """Create a short-lived, read-only embed token for the workspace (admin only)."""
    plaintext, token = embed_token_service.create_embed_token(
        db,
        api_key,
        workspace_id,
        name=payload.name,
        ttl_days=payload.ttl_days,
    )
    return EmbedTokenWithPlaintext(token=plaintext, embed_token=EmbedTokenOut.model_validate(token))


@router.get("/workspaces/{workspace_id}/embed-tokens", response_model=list[EmbedTokenOut])
def list_embed_tokens(
    workspace_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> list[EmbedTokenOut]:
    """List embed tokens for a workspace (admin only)."""
    tokens = embed_token_service.list_embed_tokens(db, api_key, workspace_id)
    return [EmbedTokenOut.model_validate(t) for t in tokens]


@router.post(
    "/workspaces/{workspace_id}/embed-tokens/{token_id}/revoke",
    response_model=EmbedTokenOut,
)
def revoke_embed_token(
    workspace_id: str,
    token_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> EmbedTokenOut:
    """Revoke an embed token (admin only)."""
    token = embed_token_service.revoke_embed_token(db, api_key, workspace_id, token_id)
    return EmbedTokenOut.model_validate(token)


@router.post(
    "/workspaces/{workspace_id}/embed-tokens/{token_id}/rotate",
    response_model=EmbedTokenWithPlaintext,
    status_code=status.HTTP_201_CREATED,
)
def rotate_embed_token(
    workspace_id: str,
    token_id: str,
    payload: EmbedTokenRotate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> EmbedTokenWithPlaintext:
    """Rotate an embed token: revoke the old one and create a replacement (admin only)."""
    plaintext, token = embed_token_service.rotate_embed_token(
        db,
        api_key,
        workspace_id,
        token_id,
        name=payload.name,
        ttl_days=payload.ttl_days,
    )
    return EmbedTokenWithPlaintext(token=plaintext, embed_token=EmbedTokenOut.model_validate(token))


@router.get("/workspaces/{workspace_id}/embed-token/current", response_model=EmbedTokenOut)
def get_current_embed_token_for_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> EmbedTokenOut:
    """Return the most recently created active embed token for the workspace."""
    tokens = embed_token_service.list_embed_tokens(db, api_key, workspace_id)
    active_tokens = [t for t in tokens if t.revoked_at is None]
    if not active_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active embed token for this workspace",
        )
    return EmbedTokenOut.model_validate(active_tokens[0])
