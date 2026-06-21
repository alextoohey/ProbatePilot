from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from schemas.estate import Alert, EstateState

LOGGER = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
SEVERITY_LABEL = {"critical": "CRITICAL", "warning": "Warning", "info": "Info"}


def email_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("EMAIL_FROM"))


def resolve_recipient(requested: str) -> str:
    """Dev/sandbox redirect: when NOTIFY_OVERRIDE_RECIPIENT is set, send every
    notification there instead of the real address. Useful with Resend's test
    tier, which only delivers to the account owner until a domain is verified."""
    override = (os.getenv("NOTIFY_OVERRIDE_RECIPIENT") or "").strip()
    return override or requested


def build_alert_digest(estate: EstateState, alerts: list[Alert]) -> tuple[str, str]:
    """Return (subject, plain-text body) summarizing the open alerts for an estate."""
    name = estate.deceasedName or "the estate"
    critical = sum(1 for a in alerts if a.severity == "critical")
    if not alerts:
        subject = f"Estate of {name}: nothing urgent right now"
    elif critical:
        subject = f"Estate of {name}: {critical} urgent item{'s' if critical != 1 else ''} need attention"
    else:
        subject = f"Estate of {name}: {len(alerts)} item{'s' if len(alerts) != 1 else ''} to review"

    lines = [
        f"Hi {estate.executor.name or 'there'},",
        "",
        f"Here is the current status for the Estate of {name}.",
        "",
    ]
    if not alerts:
        lines.append("No open deadlines or liability alerts at the moment. You're all caught up.")
    else:
        for alert in alerts:
            tag = SEVERITY_LABEL.get(alert.severity, alert.severity.title())
            days = ""
            if alert.daysRemaining is not None:
                days = f" — {alert.daysRemaining} day(s) remaining"
            lines.append(f"[{tag}] {alert.title}{days}")
            if alert.body:
                lines.append(f"  {alert.body}")
            if alert.actionRequired:
                lines.append(f"  Next step: {alert.actionRequired}")
            lines.append("")

    lines.append("— Executor AI")
    return subject, "\n".join(lines)


def build_weekly_recap(estate: EstateState, alerts: list[Alert]) -> tuple[str, str]:
    """The Monday weekly-summary email: what's open, what's done, and what's urgent.

    Identical content whether triggered on the weekly schedule or on demand."""
    name = estate.deceasedName or "the estate"
    subject = f"Your weekly estate recap — Estate of {name}"

    open_alerts = [a for a in alerts if not a.dismissed]
    critical = [a for a in open_alerts if a.severity == "critical"]
    done_tasks = [t for t in estate.tasks if t.status == "done"]
    open_tasks = [t for t in estate.tasks if t.status != "done"]

    lines = [
        f"Hi {estate.executor.name or 'there'},",
        "",
        f"Here's your weekly recap for the Estate of {name}. You're in phase {estate.phase} of 6.",
        "",
    ]

    lines.append("NEEDS YOUR ATTENTION")
    if open_alerts:
        for a in open_alerts:
            tag = SEVERITY_LABEL.get(a.severity, a.severity.title())
            days = f" — {a.daysRemaining} day(s) left" if a.daysRemaining is not None else ""
            lines.append(f"  • [{tag}] {a.title}{days}")
            if a.actionRequired:
                lines.append(f"      Next step: {a.actionRequired}")
    else:
        lines.append("  • Nothing urgent — no open deadlines or liability alerts.")
    lines.append("")

    lines.append("STILL OPEN")
    if open_tasks:
        for t in open_tasks:
            due = f" (due {t.dueDate})" if t.dueDate else ""
            lines.append(f"  • {t.title}{due}")
    else:
        lines.append("  • No outstanding tasks on file.")
    lines.append("")

    lines.append("DONE")
    if done_tasks:
        for t in done_tasks:
            lines.append(f"  • {t.title}")
    else:
        lines.append("  • Nothing marked complete yet.")
    lines.append("")

    if critical:
        lines.append(f"Bottom line: {len(critical)} critical item(s) need action before their deadline.")
    else:
        lines.append("Bottom line: no critical deadlines are at risk this week.")
    lines.append("")
    lines.append("I'll send the next recap on Monday, or you can pull one anytime from the app.")
    lines.append("")
    lines.append("— Executor AI")
    return subject, "\n".join(lines)


def send_email(to: str, subject: str, body_text: str) -> dict[str, object]:
    """Send a plain-text email via Resend when configured.

    Never raises — returns a status dict so the route can report cleanly whether
    the email went out or the provider simply isn't set up yet.
    """
    if not to:
        return {"sent": False, "reason": "missing_recipient"}
    if not email_configured():
        LOGGER.info("Email not configured (RESEND_API_KEY / EMAIL_FROM unset); skipping send to %s", to)
        return {"sent": False, "reason": "email_not_configured"}

    payload = json.dumps({
        "from": os.getenv("EMAIL_FROM"),
        "to": [to],
        "subject": subject,
        "text": body_text,
    }).encode("utf-8")
    request = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}",
            "Content-Type": "application/json",
            # Resend sits behind Cloudflare, which blocks the default
            # "Python-urllib" agent (403 error 1010) — send a real UA.
            "User-Agent": "ExecutorAI/1.0 (+https://resend.com)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
        provider_id = None
        try:
            provider_id = json.loads(body).get("id")
        except (ValueError, TypeError):
            pass
        return {"sent": True, "reason": "ok", "providerId": provider_id}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        LOGGER.warning("Resend rejected the email (%s): %s", exc.code, detail)
        return {"sent": False, "reason": f"provider_error_{exc.code}"}
    except Exception as exc:  # noqa: BLE001 - never let email failures break the request
        LOGGER.exception("Email send failed")
        return {"sent": False, "reason": f"send_failed: {exc.__class__.__name__}"}
