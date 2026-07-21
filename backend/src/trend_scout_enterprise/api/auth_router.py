"""Authentication endpoints for Microsoft Entra ID and internal sessions."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.rate_limit import limiter
from trend_scout_enterprise.core.dummy_auth import (
    create_jwt_for_user,
    exchange_dummy_code_for_user,
    get_dummy_authorization_url,
)
from trend_scout_enterprise.schemas import (
    MicrosoftAuthConfigIn,
    MicrosoftAuthConfigOut,
    LoginResponse,
)
from trend_scout_enterprise.services.auth_service import (
    create_or_update_auth_config,
    exchange_code_for_user,
    get_authorization_url,
    get_active_auth_config,
)

router = APIRouter()


@router.get("/auth/microsoft/login")
@limiter.limit("20/minute")
def microsoft_login(request: Request, state: str = "", db: Session = Depends(get_db)):
    """Redirect the user to Microsoft login or dummy login flow."""
    if settings.entra_dummy_mode:
        redirect_url = get_dummy_authorization_url(
            redirect_uri=settings.entra_redirect_uri, state=state
        )
        return RedirectResponse(url=redirect_url)

    if not get_active_auth_config(db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Microsoft authentication is not configured",
        )

    auth_url = get_authorization_url(db, state=state)
    return RedirectResponse(url=auth_url)


@router.get("/auth/microsoft/callback")
@limiter.limit("20/minute")
def microsoft_callback(request: Request, code: str, state: str = "", db: Session = Depends(get_db)):
    """Handle Microsoft OAuth2 callback and issue internal JWT."""
    if settings.entra_dummy_mode:
        user = exchange_dummy_code_for_user(code)
    else:
        user = exchange_code_for_user(db, code, redirect_uri=settings.entra_redirect_uri)

    access_token = create_jwt_for_user(user)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
        },
    )


@router.post("/auth/microsoft/config", response_model=MicrosoftAuthConfigOut)
@limiter.limit("20/minute")
def configure_microsoft_auth(
    request: Request, config_in: MicrosoftAuthConfigIn, db: Session = Depends(get_db)
):
    """Create or update the Microsoft Entra ID configuration."""
    config = create_or_update_auth_config(
        db=db,
        tenant_id=config_in.tenant_id,
        client_id=config_in.client_id,
        client_secret=config_in.client_secret,
        redirect_uri=config_in.redirect_uri,
        is_enabled=config_in.is_enabled,
    )
    return config


@router.get("/auth/microsoft/config", response_model=MicrosoftAuthConfigOut)
def get_microsoft_auth_config(db: Session = Depends(get_db)):
    """Return the current Microsoft Entra ID configuration (without secret)."""
    config = get_active_auth_config(db)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsoft authentication not configured",
        )
    return config


@router.get("/auth/me")
def get_current_user_info(db: Session = Depends(get_db)):
    """Placeholder for current user endpoint; implemented in Phase 6 with proper dependency."""
    return {"message": "Use /api/v1/settings endpoints for now"}
