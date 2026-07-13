"""API key authentication dependency."""

from fastapi import Header, HTTPException, status

from trend_scout_enterprise.core.config import settings


async def verify_api_key(x_api_key: str = Header(..., alias=settings.api_key_header)) -> str:
    """Validate the X-API-Key header against the configured secret key.

    Args:
        x_api_key: The API key provided in the request header.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 if the key is missing or invalid.
    """
    if not x_api_key or x_api_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
