"""Unit tests for password hashing."""

from app.core.security import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    hashed = hash_password("admin123")
    assert hashed != "admin123"
    assert verify_password("admin123", hashed)


def test_hash_uses_fresh_salt():
    assert hash_password("admin123") != hash_password("admin123")


def test_verify_rejects_wrong_password():
    hashed = hash_password("admin123")
    assert not verify_password("wrong-pass", hashed)


def test_verify_rejects_malformed_hash():
    assert not verify_password("admin123", "not-a-bcrypt-hash")
