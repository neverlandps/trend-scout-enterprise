"""Tests for the bcrypt dual-mode API key migration."""

import hashlib

from trend_scout_enterprise.core.security import (
    hash_api_key,
    lookup_api_key_by_plaintext,
    needs_rehash,
    verify_api_key_hash,
)
from trend_scout_enterprise.models.models import ApiKey


def _legacy_sha256(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _make_api_key(test_db, plaintext: str, stored_hash: str, key_id: str) -> ApiKey:
    api_key = ApiKey(
        id=key_id,
        name=key_id,
        key_hash=stored_hash,
        key_prefix=plaintext[:8],
        is_active=True,
        role="admin",
    )
    test_db.add(api_key)
    test_db.commit()
    return api_key


def test_verify_legacy_sha256_hash():
    plaintext = "legacy_key_1234567890"
    assert verify_api_key_hash(plaintext, _legacy_sha256(plaintext)) is True
    assert verify_api_key_hash("wrong_key", _legacy_sha256(plaintext)) is False


def test_verify_bcrypt_hash():
    plaintext = "bcrypt_key_1234567890"
    stored = hash_api_key(plaintext)
    assert stored.startswith("$2")  # bcrypt identifier
    assert verify_api_key_hash(plaintext, stored) is True
    assert verify_api_key_hash("wrong_key", stored) is False


def test_verify_invalid_hash_returns_false():
    assert verify_api_key_hash("anything", "not-a-valid-hash") is False


def test_needs_rehash():
    plaintext = "rehash_key_1234567890"
    assert needs_rehash(_legacy_sha256(plaintext)) is True
    assert needs_rehash(hash_api_key(plaintext)) is False


def test_lookup_legacy_key_auto_upgrades_to_bcrypt(test_db):
    plaintext = "legacy_lookup_key_0001"
    api_key = _make_api_key(test_db, plaintext, _legacy_sha256(plaintext), "legacy-key")

    found = lookup_api_key_by_plaintext(test_db, plaintext)
    assert found is not None
    assert found.id == api_key.id

    # Hash was transparently upgraded to bcrypt in the database.
    test_db.refresh(api_key)
    assert api_key.key_hash.startswith("$2")
    assert needs_rehash(api_key.key_hash) is False
    assert verify_api_key_hash(plaintext, api_key.key_hash) is True


def test_lookup_bcrypt_key(test_db):
    plaintext = "bcrypt_lookup_key_001"
    api_key = _make_api_key(test_db, plaintext, hash_api_key(plaintext), "bcrypt-key")

    found = lookup_api_key_by_plaintext(test_db, plaintext)
    assert found is not None
    assert found.id == api_key.id


def test_lookup_rejects_wrong_key(test_db):
    plaintext = "correct_lookup_key_01"
    _make_api_key(test_db, plaintext, hash_api_key(plaintext), "right-key")

    # Same prefix, different key: must not match.
    wrong = plaintext[:8] + "_wrong_suffix"
    assert lookup_api_key_by_plaintext(test_db, wrong) is None
    # Completely unknown key: must not match.
    assert lookup_api_key_by_plaintext(test_db, "totally_unknown_key") is None
