"""Shared FastAPI dependencies: session auth and estate-ownership checks.

Sessions are opaque tokens issued by ``POST /auth/login`` (or ``/auth/demo``)
and carried by the web layer as a cookie, forwarded here as
``Authorization: Bearer <token>``.

Every estate-scoped route must call `ensure_estate_access` (directly, or via
the `require_estate_access` path-param dependency) before touching estate
data. The one exception is the seeded demo estate, which stays readable
without a session so a portfolio visitor can click "Try the demo" without
registering.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from schemas.auth import User
from store.redis_client import DEFAULT_ESTATE_ID, get_session_user_id, get_user

DEMO_ESTATE_ID = DEFAULT_ESTATE_ID


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


async def optional_user(authorization: str | None = Header(default=None)) -> User | None:
    """Resolve the caller's session without requiring one. Routes that are
    public-with-an-ownership-exception (estate access) depend on this
    instead of `require_user` so an anonymous demo visitor still resolves
    to `None` rather than a 401."""
    token = _bearer_token(authorization)
    user_id = get_session_user_id(token) if token else None
    return get_user(user_id) if user_id else None


async def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def ensure_estate_access(estate_id: str, user: User | None) -> None:
    """Raise if `user` may not read/write `estate_id`.

    The demo estate is always readable. Every other estate requires a
    session, and the estate must be in that user's `estateIds`. A
    non-owned estate reports 404 rather than 403 so ownership can't be
    probed by estate id.
    """
    if estate_id == DEMO_ESTATE_ID:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if estate_id not in user.estateIds:
        raise HTTPException(status_code=404, detail="Estate not found")


async def require_estate_access(estate_id: str, user: User | None = Depends(optional_user)) -> User | None:
    """Dependency for routes where `estate_id` is a URL path segment —
    FastAPI binds it from the path automatically by parameter name."""
    ensure_estate_access(estate_id, user)
    return user
