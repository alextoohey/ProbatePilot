from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException

from agents.deadline_agent import refresh_deadline_state
from api.deps import require_user
from auth.security import hash_password, new_session_token, verify_password
from constants import DEMO_VISITOR_TTL_SECONDS
from schemas.auth import AuthResponse, LoginRequest, MeResponse, PublicUser, RegisterRequest, User
from schemas.estate import EstateState, Executor
from seed.demo_estate import build_demo_estate_for_visitor
from store.redis_client import (
    create_session,
    create_user,
    delete_session,
    get_estate_state,
    get_user_by_email,
    set_estate_state,
    update_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _create_estate_for_user(user: User, request: RegisterRequest) -> EstateState:
    """Create the user's first estate from their sign-up details. Jurisdiction
    is California-only for the hackathon, regardless of the chosen state."""
    estate = EstateState(
        id=f"est-{uuid.uuid4().hex[:8]}",
        deceasedName=request.deceasedName.strip() or "Unknown Decedent",
        dateOfDeath=request.dateOfDeath or date.today().isoformat(),
        appointmentDate=date.today().isoformat(),
        executor=Executor(name=user.name, email=user.email),
        county=user.county,
        phase=1,
    )
    return set_estate_state(estate)


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest) -> AuthResponse:
    if get_user_by_email(request.email) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(
        id=f"user-{uuid.uuid4().hex[:12]}",
        name=request.name.strip(),
        email=str(request.email).strip().lower(),
        phone=request.phone,
        passwordHash=hash_password(request.password),
        relationship=request.relationship,
        state=request.state,
        county=request.county,
    )
    create_user(user)

    estate = _create_estate_for_user(user, request)
    user.estateIds = [estate.id]
    update_user(user)

    token = create_session(user.id, new_session_token())
    return AuthResponse(token=token, user=PublicUser.from_user(user), estate=estate)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest) -> AuthResponse:
    user = get_user_by_email(str(request.email))
    if user is None or not verify_password(request.password, user.passwordHash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_session(user.id, new_session_token())
    return AuthResponse(token=token, user=PublicUser.from_user(user))


@router.post("/demo", response_model=AuthResponse)
async def demo_login() -> AuthResponse:
    """Guest entry point for portfolio visitors: every call mints its own
    independent copy of the seeded Robert Milligan estate plus its own
    throwaway user, so one visitor's edits (completed tasks, uploads) never
    show up for another. No registration step. Both records are ephemeral —
    they self-expire in the store after `DEMO_VISITOR_TTL_SECONDS` rather
    than needing a cleanup job."""
    visitor_id = uuid.uuid4().hex[:10]
    estate = build_demo_estate_for_visitor(f"demo-{visitor_id}")
    estate = set_estate_state(estate)  # isDemo=True gives it a self-renewing TTL automatically

    # Evaluate deadlines up front so the visitor lands on a populated dashboard
    # instead of an empty one. The deterministic rule engine only (no Claude
    # tool-use loop) keeps this instant — full run_deadline_agent() takes
    # 30-45s end to end, which is not acceptable to block a login on.
    refresh_deadline_state(estate.id)
    estate = get_estate_state(estate.id)

    user = User(
        id=f"user-demo-{visitor_id}",
        name=estate.executor.name,
        email=f"demo+{visitor_id}@probatepilot.app",
        passwordHash=hash_password(uuid.uuid4().hex),
        estateIds=[estate.id],
    )
    create_user(user, ttl_seconds=DEMO_VISITOR_TTL_SECONDS)

    token = create_session(user.id, new_session_token(), ttl_seconds=DEMO_VISITOR_TTL_SECONDS)
    return AuthResponse(token=token, user=PublicUser.from_user(user), estate=estate)


@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    token = _bearer_token(authorization)
    if token:
        delete_session(token)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(require_user)) -> MeResponse:
    estates: list[EstateState] = []
    for estate_id in user.estateIds:
        try:
            estates.append(get_estate_state(estate_id))
        except KeyError:
            continue
    return MeResponse(user=PublicUser.from_user(user), estates=estates)
