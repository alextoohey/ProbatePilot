from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from agents.deadline_agent import run_deadline_agent
from api.deps import require_estate_access, require_user
from schemas.auth import CreateEstateRequest, User
from schemas.api import EstateResponse
from schemas.estate import EstateState, Executor
from store.redis_client import get_estate_state, seed_demo_estate, set_estate_state, update_user

router = APIRouter(tags=["estates"])


@router.post("/seed")
async def seed() -> dict[str, object]:
    """Reset the public demo estate to its known-good seed state. Always
    operates on the demo estate only — there is no way to pass an arbitrary
    estate id, so this can safely stay unauthenticated."""
    estate = seed_demo_estate()
    alerts = await run_deadline_agent(estate.id)
    return {"estate": get_estate_state(estate.id), "alerts": alerts}


@router.get("/estate/{estate_id}", dependencies=[Depends(require_estate_access)])
async def estate(estate_id: str) -> dict[str, object]:
    try:
        return {"estate": get_estate_state(estate_id)}
    except KeyError as exc:
        # Access was already authorized by require_estate_access; this only
        # fires if a user's estateIds points at a record that no longer
        # exists.
        raise HTTPException(status_code=404, detail="Estate not found") from exc


@router.post("/estates", response_model=EstateResponse)
async def create_estate(request: CreateEstateRequest, user: User = Depends(require_user)) -> EstateResponse:
    """Persist a new estate and attach it to the authenticated user."""
    estate_state = EstateState(
        id=f"est-{uuid.uuid4().hex[:12]}",
        deceasedName=request.deceasedName.strip(),
        dateOfDeath=request.dateOfDeath or date.today().isoformat(),
        appointmentDate=date.today().isoformat(),
        state="california",
        county=(request.county or "").strip() or None,
        executor=Executor(name=user.name, email=user.email),
        phase=1,
    )
    estate_state = set_estate_state(estate_state)
    if estate_state.id not in user.estateIds:
        user.estateIds.append(estate_state.id)
        update_user(user)
    return EstateResponse(estate=estate_state)
