"""Password hashing — bcrypt wrappers used by the auth service."""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password with a fresh bcrypt salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plaintext matches the stored bcrypt hash.

    Malformed stored hashes and passwords outside bcrypt's 72-byte limit
    surface as ValueError and are treated as a failed match.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
