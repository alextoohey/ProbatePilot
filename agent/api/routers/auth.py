from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException

from api.deps import DEMO_ESTATE_ID, require_user
from auth.security import hash_password, new_session_token, verify_password
from schemas.auth import AuthResponse, LoginRequest, MeResponse, PublicUser, RegisterRequest, User
from schemas.estate import EstateState, Executor
from store.redis_client import (
    create_session,
    create_user,
    delete_session,
    get_estate_state,
    get_session_user_id,
    get_user,
    get_user_by_email,
    set_estate_state,
    update_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_USER_EMAIL = "demo@probatepilot.app"


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
    """Guest entry point for portfolio visitors: signs into a shared demo
    account scoped to the seeded Robert Milligan estate, with no
    registration step. The demo estate is world-readable regardless (see
    `api.deps.ensure_estate_access`); this endpoint exists so the frontend
    can put the visitor through the exact same authenticated flow as a real
    user instead of special-casing "no session" in every screen."""
    estate = get_estate_state(DEMO_ESTATE_ID)  # auto-seeds on first call

    user = get_user_by_email(DEMO_USER_EMAIL)
    if user is None:
        user = User(
            id=f"user-demo-{uuid.uuid4().hex[:8]}",
            name=estate.executor.name,
            email=DEMO_USER_EMAIL,
            passwordHash=hash_password(uuid.uuid4().hex),
            estateIds=[DEMO_ESTATE_ID],
        )
        create_user(user)
    elif DEMO_ESTATE_ID not in user.estateIds:
        user.estateIds.append(DEMO_ESTATE_ID)
        update_user(user)

    token = create_session(user.id, new_session_token())
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
