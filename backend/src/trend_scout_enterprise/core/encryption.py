"""Fernet encryption utilities for API keys and credentials."""

import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from trend_scout_enterprise.core.config import settings


_SALT_ENV_VAR = "ENCRYPTION_SALT"
_KDF_ITERATIONS = 100_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from a password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def _get_salt() -> bytes:
    """Return the encryption salt from env or fall back to secret key prefix."""
    salt_b64 = os.environ.get(_SALT_ENV_VAR, "")
    if salt_b64:
        return base64.urlsafe_b64decode(salt_b64)
    return settings.secret_key.encode()[:16]


def _get_fernet() -> Fernet:
    """Return a Fernet instance derived from the configured secret key."""
    salt = _get_salt()
    key = _derive_key(settings.secret_key, salt)
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext string."""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        raise ValueError(f"Decryption failed: {exc}") from exc


def encrypt_dict(data: dict[str, Any]) -> str:
    """Serialize and encrypt a dictionary."""
    plaintext = json.dumps(data)
    return encrypt_value(plaintext)


def decrypt_dict(ciphertext: str) -> dict[str, Any]:
    """Decrypt and deserialize a dictionary."""
    plaintext = decrypt_value(ciphertext)
    return json.loads(plaintext)


def mask_sensitive_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of config with known sensitive keys masked for display."""
    sensitive_keys = {"api_key", "token", "password", "secret", "credentials"}
    masked = {}
    for key, value in config.items():
        if isinstance(key, str) and any(s in key.lower() for s in sensitive_keys):
            masked[key] = "***" if value else value
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_config(value)
        else:
            masked[key] = value
    return masked
