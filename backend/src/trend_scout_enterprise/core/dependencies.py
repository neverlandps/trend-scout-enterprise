"""Shared FastAPI dependencies."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import hash_api_key
from trend_scout_enterprise.models.models import ApiKey, Workspace
from trend_scout_enterprise.services import workspace_service


async def get_current_workspace(
    x_workspace_id: str | None = Header(None, alias=settings.workspace_id_header),
    x_api_key: str = Header(..., alias=settings.api_key_header),
    db: Session = Depends(get_db),
) -> Workspace:
    """Resolve the authenticated API key and its requested/default workspace."""
    key_hash = hash_api_key(x_api_key)
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash, ApiKey.is_active == True
    ).first()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    api_key.last_used_at = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(api_key)
    return workspace_service.resolve_workspace(db, api_key, x_workspace_id)


async def get_current_api_key(
    x_api_key: str = Header(..., alias=settings.api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Resolve the API key to an ApiKey entity."""
    key_hash = hash_api_key(x_api_key)
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash, ApiKey.is_active == True
    ).first()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    api_key.last_used_at = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(api_key)
    return api_key
