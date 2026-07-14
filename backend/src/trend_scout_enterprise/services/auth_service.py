"""Authentication service for Entra ID and local JWT sessions."""

from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.encryption import encrypt_value, decrypt_value
from trend_scout_enterprise.models.auth import MicrosoftAuthConfig


def get_active_auth_config(db: Session) -> MicrosoftAuthConfig | None:
    """Return the enabled Microsoft auth config, if any."""
    return db.query(MicrosoftAuthConfig).filter(
        MicrosoftAuthConfig.is_enabled == True
    ).first()


def get_authorization_url(db: Session, state: str = "") -> str:
    """Build Microsoft OAuth2 authorization URL from active config."""
    config = get_active_auth_config(db)
    if config is None:
        raise ValueError("Microsoft authentication is not configured or enabled")
    return (
        f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/authorize"
        f"?client_id={config.client_id}"
        f"&response_type=code"
        f"&redirect_uri={config.redirect_uri}"
        f"&response_mode=query"
        f"&scope=openid profile email User.Read"
        f"&state={state}"
    )


def exchange_code_for_user(db: Session, code: str, redirect_uri: str) -> dict:
    """Exchange Microsoft authorization code for user profile.

    This uses the client credentials flow with the Microsoft token endpoint.
    """
    import requests

    config = get_active_auth_config(db)
    if config is None:
        raise ValueError("Microsoft authentication is not configured or enabled")

    client_secret = decrypt_value(config.client_secret_encrypted)
    token_url = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri or config.redirect_uri,
    }
    response = requests.post(token_url, data=payload, timeout=30)
    response.raise_for_status()
    token_data = response.json()

    id_token = token_data.get("id_token")
    if not id_token:
        raise ValueError("Microsoft token response did not include id_token")

    # Decode the id_token without verification (Microsoft verifies it for us)
    from jose import jwt
    claims = jwt.get_unverified_claims(id_token)
    return {
        "id": claims.get("oid"),
        "entra_object_id": claims.get("oid"),
        "email": claims.get("email") or claims.get("upn"),
        "name": claims.get("name"),
    }


def create_or_update_auth_config(
    db: Session,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    is_enabled: bool = True,
) -> MicrosoftAuthConfig:
    """Upsert the Microsoft auth configuration."""
    existing = db.query(MicrosoftAuthConfig).filter(
        MicrosoftAuthConfig.is_default == True
    ).first()
    if existing:
        existing.tenant_id = tenant_id
        existing.client_id = client_id
        existing.client_secret_encrypted = encrypt_value(client_secret)
        existing.redirect_uri = redirect_uri
        existing.is_enabled = is_enabled
        db.commit()
        db.refresh(existing)
        return existing

    config = MicrosoftAuthConfig(
        id=__import__("uuid").uuid4().hex,
        name="default",
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret_encrypted=encrypt_value(client_secret),
        redirect_uri=redirect_uri,
        is_enabled=is_enabled,
        is_default=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
