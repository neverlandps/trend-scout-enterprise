"""Dummy Microsoft OAuth2 provider for local development and testing."""

import json
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


def _load_public_keys() -> dict[str, str]:
    """Parse ``jwt_public_keys_pem`` (JSON dict of kid -> public key PEM)."""
    try:
        keys = json.loads(settings.jwt_public_keys_pem)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid JWT") from exc
    if not isinstance(keys, dict):
        raise ValueError("Invalid JWT")
    return keys


def create_jwt_for_user(user: dict) -> str:
    """Issue an internal JWT for a user.

    Signs with RS256 (plus a ``kid`` header for key rotation) when
    ``jwt_private_key_pem`` is configured; otherwise falls back to the
    symmetric algorithm (HS256) with ``secret_key`` for backward
    compatibility in local development and testing.
    """
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
    if settings.jwt_private_key_pem:
        return jwt.encode(
            payload,
            settings.jwt_private_key_pem,
            algorithm="RS256",
            headers={"kid": settings.jwt_key_id},
        )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    """Decode and validate internal JWT.

    Reads the token header first: RS256 tokens are verified against the
    public key matching the ``kid`` claim in ``jwt_public_keys_pem`` (so old
    keys remain valid during rotation); HS256 tokens are verified with
    ``secret_key``. Unknown kids and unsupported algorithms are rejected.

    Raises a generic ValueError on failure; the underlying jose exception is
    logged but never exposed to callers so internal details are not leaked
    into HTTP responses.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg == "RS256":
            kid = header.get("kid")
            public_keys = _load_public_keys()
            key_pem = public_keys.get(kid)
            if not key_pem:
                raise ValueError("Invalid JWT")
            return jwt.decode(token, key_pem, algorithms=["RS256"])
        if alg == "HS256":
            return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        raise ValueError("Invalid JWT")
    except ValueError:
        raise
    except Exception as exc:
        logger.warning("dummy_auth_jwt_decode_failed", error=str(exc))
        raise ValueError("Invalid JWT") from exc
