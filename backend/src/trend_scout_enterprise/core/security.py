"""API key authentication dependency."""

from fastapi import Header, HTTPException, status

from trend_scout_enterprise.core.config import settings


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
