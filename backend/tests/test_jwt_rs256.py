"""Tests for RS256 JWT signing and key rotation in core.dummy_auth."""

import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.dummy_auth import DUMMY_USER, create_jwt_for_user, decode_jwt


def _generate_key_pair() -> tuple[str, str]:
    """Return (private_pem, public_pem) for a fresh RSA 2048 key pair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def rs256_keys(monkeypatch):
    """Configure RS256 signing with two public keys (kid rotation window)."""
    private_pem, public_pem = _generate_key_pair()
    _, old_public_pem = _generate_key_pair()
    monkeypatch.setattr(settings, "jwt_private_key_pem", private_pem)
    monkeypatch.setattr(settings, "jwt_key_id", "kid-new")
    monkeypatch.setattr(
        settings,
        "jwt_public_keys_pem",
        json.dumps({"kid-old": old_public_pem, "kid-new": public_pem}),
    )
    return {"private_pem": private_pem, "public_pem": public_pem}


class TestRS256RoundTrip:
    def test_rs256_sign_and_verify(self, rs256_keys):
        token = create_jwt_for_user(DUMMY_USER)
        header = jose_jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"
        assert header["kid"] == "kid-new"

        payload = decode_jwt(token)
        assert payload["sub"] == DUMMY_USER["id"]
        assert payload["email"] == DUMMY_USER["email"]

    def test_rs256_tampered_token_rejected(self, rs256_keys):
        token = create_jwt_for_user(DUMMY_USER)
        parts = token.split(".")
        tampered = f"{parts[0]}.{parts[1]}.invalidsignature"
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_jwt(tampered)


class TestKeyRotation:
    def test_old_kid_public_key_still_verifies(self, rs256_keys, monkeypatch):
        """A token signed under the old kid validates while its public key remains."""
        old_private_pem, old_public_pem = _generate_key_pair()
        monkeypatch.setattr(
            settings,
            "jwt_public_keys_pem",
            json.dumps(
                {**json.loads(settings.jwt_public_keys_pem), "kid-old": old_public_pem}
            ),
        )
        old_token = jose_jwt.encode(
            {"sub": "user-x", "exp": 9999999999},
            old_private_pem,
            algorithm="RS256",
            headers={"kid": "kid-old"},
        )
        assert decode_jwt(old_token)["sub"] == "user-x"

    def test_removed_kid_rejected(self, rs256_keys):
        """Once the old public key is removed, its tokens are rejected."""
        other_private_pem, _ = _generate_key_pair()
        token = jose_jwt.encode(
            {"sub": "user-x", "exp": 9999999999},
            other_private_pem,
            algorithm="RS256",
            headers={"kid": "kid-removed"},
        )
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_jwt(token)

    def test_wrong_public_key_rejected(self, rs256_keys):
        """A token signed with a different private key fails verification."""
        other_private_pem, _ = _generate_key_pair()
        token = jose_jwt.encode(
            {"sub": "user-x", "exp": 9999999999},
            other_private_pem,
            algorithm="RS256",
            headers={"kid": "kid-new"},
        )
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_jwt(token)


class TestHS256BackwardCompatibility:
    def test_hs256_default_sign_and_verify(self):
        """Without a configured private key, signing falls back to HS256."""
        token = create_jwt_for_user(DUMMY_USER)
        header = jose_jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

        payload = decode_jwt(token)
        assert payload["sub"] == DUMMY_USER["id"]

    def test_hs256_token_accepted_while_rs256_configured(self, rs256_keys):
        """HS256 tokens remain valid during an RS256 migration window."""
        token = jose_jwt.encode(
            {"sub": "user-y", "exp": 9999999999},
            settings.secret_key,
            algorithm="HS256",
        )
        assert decode_jwt(token)["sub"] == "user-y"

    def test_hs256_wrong_secret_rejected(self):
        token = jose_jwt.encode(
            {"sub": "user-y", "exp": 9999999999},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_jwt(token)


class TestDecodeEdgeCases:
    def test_garbage_token_rejected(self):
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_jwt("not-a-jwt")

    def test_unsupported_algorithm_rejected(self):
        token = jose_jwt.encode(
            {"sub": "user-z", "exp": 9999999999},
            "secret",
            algorithm="HS384",
        )
        with pytest.raises(ValueError, match="Invalid JWT"):
            decode_jwt(token)
