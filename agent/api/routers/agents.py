from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agents.deadline_agent import mark_alert_complete, refresh_deadline_state, run_deadline_agent
from api.deps import ensure_estate_access, optional_user
from observability.phoenix import span
from researcher.research_agent import run_research_agent
from schemas.api import CompleteAlertRequest, DeadlineAgentRequest, EstateResponse, ResearchAgentRequest, ResearchAgentResponse
from schemas.auth import User
from store.redis_client import get_estate_state

router = APIRouter(tags=["agents"])


@router.post("/deadline-agent")
async def deadline_agent(request: DeadlineAgentRequest, user: User | None = Depends(optional_user)) -> dict[str, object]:
    ensure_estate_access(request.estateId, user)
    with span("route.deadline_agent", estate_id=request.estateId, action_type="deadline_agent_run"):
        alerts = await run_deadline_agent(request.estateId)
        return {"estateId": request.estateId, "alerts": alerts}


@router.post("/research-agent", response_model=ResearchAgentResponse)
async def research_agent(request: ResearchAgentRequest, user: User | None = Depends(optional_user)) -> ResearchAgentResponse:
    ensure_estate_access(request.estateId, user)
    with span("route.research_agent", estate_id=request.estateId, action_type="research_agent_run"):
        result = await run_research_agent(request.estateId, force=request.force)
        return ResearchAgentResponse(estateId=request.estateId, result=result.model_dump(mode="json"))


@router.post("/complete-alert", response_model=EstateResponse)
async def complete_alert(request: CompleteAlertRequest, user: User | None = Depends(optional_user)) -> EstateResponse:
    ensure_estate_access(request.estateId, user)
    with span("route.complete_alert", estate_id=request.estateId, action_type="complete_alert", alert_id=request.alertId):
        try:
            mark_alert_complete(request.estateId, request.alertId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        refresh_deadline_state(request.estateId)
        return EstateResponse(estate=get_estate_state(request.estateId))
