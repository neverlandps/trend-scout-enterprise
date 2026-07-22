"""Dummy Microsoft OAuth2 provider for local development and testing."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog
from jose import jwt

from trend_scout_enterprise.core.config import settings

logger = structlog.get_logger(__name__)

DUMMY_USER = {
    "id": "dummy-user-001",
    "entra_object_id": "00000000-0000-0000-0000-000000000001",
    "email": "dummy.user@example.com",
    "name": "Dummy User",
}


def get_dummy_authorization_url(redirect_uri: str, state: str = "") -> str:
    """Return a local redirect that simulates Microsoft authorization completion."""
    return f"{redirect_uri}?code=dummy-auth-code&state={state}"


def exchange_dummy_code_for_user(code: str) -> dict:
    """Return the dummy user profile for any 'code'."""
    if code != "dummy-auth-code":
        raise ValueError("Invalid dummy authorization code")
    return DUMMY_USER.copy()


def create_jwt_for_user(user: dict) -> str:
    """Issue an internal JWT for a user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "oid": user["entra_object_id"],
        "email": user["email"],
        "name": user.get("name"),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    """Decode and validate internal JWT.

    Raises a generic ValueError on failure; the underlying jose exception is
    logged but never exposed to callers so internal details are not leaked
    into HTTP responses.
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except Exception as exc:
        logger.warning("dummy_auth_jwt_decode_failed", error=str(exc))
        raise ValueError("Invalid JWT") from exc
