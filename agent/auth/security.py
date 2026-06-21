from __future__ import annotations

import secrets

import bcrypt

# bcrypt truncates silently at 72 bytes; guard so long passwords still hash the
# full input rather than only the first 72 bytes.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash for ``password`` (utf-8, decoded to str)."""
    payload = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of ``password`` against a stored bcrypt hash."""
    try:
        payload = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(payload, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    """A URL-safe, unguessable opaque session token."""
    return secrets.token_urlsafe(32)
