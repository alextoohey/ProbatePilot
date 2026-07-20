from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agents.deadline_agent import run_deadline_agent
from api.deps import ensure_estate_access, optional_user
from notify.email import build_alert_digest, build_weekly_recap, email_configured, resolve_recipient, send_email
from observability.phoenix import set_span_attribute, span
from schemas.api import NotifyEmailRequest, NotifyEmailResponse
from schemas.auth import User
from store.redis_client import get_estate_state

router = APIRouter(tags=["notify"])


@router.post("/notify/email")
async def notify_email(request: NotifyEmailRequest, user: User | None = Depends(optional_user)) -> NotifyEmailResponse:
    """Email the executor a digest of the estate's current deadline/liability alerts."""
    ensure_estate_access(request.estateId, user)
    with span("route.notify_email", estate_id=request.estateId, action_type="notify_email") as current_span:
        try:
            estate_state = get_estate_state(request.estateId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Estate not found") from exc
        recipient = resolve_recipient((request.recipientEmail or estate_state.executor.email or "").strip())
        # Fresh alerts straight from the DeadlineAgent — same source as the dashboard.
        alerts = await run_deadline_agent(request.estateId)
        if request.kind == "weekly":
            subject, body = build_weekly_recap(estate_state, alerts)
        else:
            subject, body = build_alert_digest(estate_state, alerts)
        result = send_email(recipient, subject, body)
        set_span_attribute(current_span, "email_configured", email_configured())
        set_span_attribute(current_span, "email_sent", bool(result.get("sent")))
        set_span_attribute(current_span, "alert_count", len(alerts))
        set_span_attribute(current_span, "email_kind", request.kind)
        return NotifyEmailResponse(
            estateId=request.estateId,
            sent=bool(result.get("sent")),
            reason=str(result.get("reason", "unknown")),
            recipient=recipient or None,
            alertCount=len(alerts),
            subject=subject,
            body=body,
        )
