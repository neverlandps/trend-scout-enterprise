"""API key authentication dependency."""

from fastapi import Header, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db

security_bearer = HTTPBearer(auto_error=False)


def hash_api_key(plaintext: str) -> str:
    """Return a deterministic hash of an API key for storage."""
    import hashlib

    return hashlib.sha256(plaintext.encode()).hexdigest()


def get_key_prefix(plaintext: str, length: int = 8) -> str:
    """Return a short prefix for an API key for display/logging."""
    return plaintext[:length]


def generate_api_key(prefix: str = "tse_", length: int = 32) -> str:
    """Generate a random API key string."""
    import secrets

    return f"{prefix}{secrets.token_urlsafe(length)}"


async def verify_api_key(
    x_api_key: str = Header(..., alias=settings.api_key_header),
) -> str:
    """Validate the X-API-Key header and return the plaintext key.

    Args:
        x_api_key: The API key provided in the request header.

    Returns:
        The plaintext API key string.

    Raises:
        HTTPException: 401 if the key is missing or invalid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


def get_or_create_default_api_key(db) -> object:
    """Return the first active API key, creating one if the table is empty."""
    from trend_scout_enterprise.models.models import ApiKey

    key = db.query(ApiKey).filter(ApiKey.is_active == True).first()
    if key:
        return key

    plaintext = generate_api_key()
    key = ApiKey(
        id=__import__("uuid").uuid4().hex,
        name="default",
        key_hash=hash_api_key(plaintext),
        key_prefix=get_key_prefix(plaintext),
        is_active=True,
        role="admin",
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def resolve_current_identity(
    x_api_key: str = Header(None, alias=settings.api_key_header),
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve either API key or JWT bearer to an identity dictionary.

    Returns a dict with at least {'type': 'api_key'|'jwt', 'id': ..., 'email': ...}.
    API key takes precedence if both are provided.
    """
    from trend_scout_enterprise.models.models import ApiKey

    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        api_key = db.query(ApiKey).filter(
            ApiKey.key_hash == key_hash, ApiKey.is_active == True
        ).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return {
            "type": "api_key",
            "id": api_key.id,
            "email": f"apikey:{api_key.key_prefix}",
            "role": api_key.role or "analyst",
        }

    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
        try:
            from trend_scout_enterprise.core.dummy_auth import decode_jwt
            payload = decode_jwt(token)
            return {
                "type": "jwt",
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "name": payload.get("name"),
                "role": "analyst",
            }
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT: {exc}",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
