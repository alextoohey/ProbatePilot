from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

from schemas.estate import Alert, EstateState

LOGGER = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
SEVERITY_LABEL = {"critical": "CRITICAL", "warning": "Warning", "info": "Info"}
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

# A plain signature block, so every notification closes like a note from a real
# person on an estate-support team rather than an automated dump.
SIGNATURE = "Warmly,\nThe Executor AI team"
FOOTER = (
    "—\n"
    "Executor AI · Estate administration support\n"
    "You're receiving this because you're the named executor on this estate. "
    "Just reply to this email if you'd like a hand with anything."
)


def _first_name(full_name: str | None) -> str:
    """Greet by first name the way a person would, falling back gracefully."""
    name = (full_name or "").strip()
    return name.split()[0] if name else "there"


def _fmt_date(value: str | None) -> str | None:
    """Render an ISO date as 'Friday, June 27' — how a person writes a deadline."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None
    return parsed.strftime("%A, %B %-d")


def _due_from_days(days: int | None) -> str | None:
    """Turn 'daysRemaining' into a concrete calendar date the reader can act on."""
    if days is None:
        return None
    try:
        return (date.today() + timedelta(days=int(days))).strftime("%A, %B %-d")
    except (ValueError, TypeError, OverflowError):
        return None


def _days_since(value: str | None) -> int | None:
    try:
        parsed = datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None
    return (date.today() - parsed).days


def email_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("EMAIL_FROM"))


def resolve_recipient(requested: str) -> str:
    """Dev/sandbox redirect: when NOTIFY_OVERRIDE_RECIPIENT is set, send every
    notification there instead of the real address. Useful with Resend's test
    tier, which only delivers to the account owner until a domain is verified."""
    override = (os.getenv("NOTIFY_OVERRIDE_RECIPIENT") or "").strip()
    return override or requested


def build_alert_digest(estate: EstateState, alerts: list[Alert]) -> tuple[str, str]:
    """Return (subject, plain-text body) for an on-demand reminder of open items.

    Written to read like a short note from an estate-support team — concrete
    deadlines, the one next step, and nothing that sounds machine-generated."""
    name = estate.deceasedName or "the estate"
    first = _first_name(estate.executor.name)
    open_alerts = sorted(
        (a for a in alerts if not a.dismissed),
        key=lambda a: (SEVERITY_ORDER.get(a.severity, 9), a.daysRemaining if a.daysRemaining is not None else 999),
    )
    critical = sum(1 for a in open_alerts if a.severity == "critical")

    if not open_alerts:
        subject = f"You're all caught up — Estate of {name}"
    elif critical:
        soonest = next((a.daysRemaining for a in open_alerts if a.severity == "critical" and a.daysRemaining is not None), None)
        when = f"{soonest} days" if soonest is not None else "soon"
        subject = f"Time-sensitive: {critical} item{'s' if critical != 1 else ''} due in {when} — Estate of {name}"
    else:
        subject = f"A quick reminder on the Estate of {name}"

    lines = [f"Hi {first},", ""]

    if not open_alerts:
        lines += [
            f"Just a quick check-in on the Estate of {name}: there's nothing time-sensitive "
            "on your plate right now, and no deadlines at risk. Nicely done.",
            "",
            "I'll be in touch the moment something needs your attention.",
        ]
    else:
        lead = (
            "I wanted to flag a few things on the Estate of "
            f"{name} that have a deadline attached, so nothing slips by:"
        )
        lines += [lead, ""]
        for a in open_alerts:
            due = _due_from_days(a.daysRemaining)
            if a.daysRemaining is not None and due:
                timing = f" Due {due} ({a.daysRemaining} days left)."
            elif a.daysRemaining is not None:
                timing = f" {a.daysRemaining} days left."
            else:
                timing = ""
            lines.append(f"• {a.title}.{timing}")
            if a.body:
                lines.append(f"  {a.body}")
            if a.actionRequired:
                lines.append(f"  What to do: {a.actionRequired}")
            lines.append("")
        if critical:
            lines.append(
                "A couple of these are tied to California probate deadlines, and missing them "
                "can leave you personally on the hook — so they're worth handling first."
            )
            lines.append("")
        lines.append("If you'd like, open the dashboard and I'll walk you through the next step.")

    lines += ["", SIGNATURE, "", FOOTER]
    return subject, "\n".join(lines)


def build_weekly_recap(estate: EstateState, alerts: list[Alert]) -> tuple[str, str]:
    """The Monday weekly-summary email: where things stand, what's urgent, what's done.

    Reads like a weekly check-in from a case manager, not a status dump.
    Identical content whether triggered on the weekly schedule or on demand."""
    name = estate.deceasedName or "the estate"
    first = _first_name(estate.executor.name)

    open_alerts = sorted(
        (a for a in alerts if not a.dismissed),
        key=lambda a: (SEVERITY_ORDER.get(a.severity, 9), a.daysRemaining if a.daysRemaining is not None else 999),
    )
    critical = [a for a in open_alerts if a.severity == "critical"]
    done_tasks = [t for t in estate.tasks if t.status == "done"]
    open_tasks = [t for t in estate.tasks if t.status != "done"]

    if critical:
        n = len(critical)
        subject = f"{n} thing{'s' if n != 1 else ''} need your attention this week — Estate of {name}"
    else:
        subject = f"Your weekly check-in — Estate of {name}"

    # Opening: orient them in time and progress the way a person would.
    days_in = _days_since(estate.appointmentDate)
    if days_in is not None and days_in >= 0:
        context = f"It's been {days_in} days since you were appointed, and you're {estate.phase} of 6 phases through the estate."
    else:
        context = f"You're {estate.phase} of 6 phases through the Estate of {name}."

    lines = [
        f"Hi {first},",
        "",
        f"Here's your weekly check-in on the Estate of {name}. {context} "
        "Here's where things stand and what's worth doing next.",
        "",
    ]

    # What needs attention — the part that actually matters first.
    lines.append("What needs your attention")
    if open_alerts:
        for a in open_alerts:
            due = _due_from_days(a.daysRemaining)
            if a.daysRemaining is not None and due:
                timing = f" — due {due}, {a.daysRemaining} days out"
            elif a.daysRemaining is not None:
                timing = f" — {a.daysRemaining} days out"
            else:
                timing = ""
            lines.append(f"  • {a.title}{timing}")
            if a.actionRequired:
                lines.append(f"    What to do: {a.actionRequired}")
    else:
        lines.append("  • Nothing pressing — no open deadlines or liability flags. You're in good shape.")
    lines.append("")

    # Still on your list.
    lines.append("Still on your list")
    if open_tasks:
        for t in open_tasks:
            due = _fmt_date(t.dueDate)
            lines.append(f"  • {t.title}" + (f" (due {due})" if due else ""))
    else:
        lines.append("  • Nothing outstanding right now.")
    lines.append("")

    # Already handled — a little credit goes a long way for someone grieving.
    lines.append("Already taken care of")
    if done_tasks:
        for t in done_tasks:
            lines.append(f"  • {t.title}")
    else:
        lines.append("  • We'll start checking things off here as you go.")
    lines.append("")

    if critical:
        n = len(critical)
        lines.append(
            f"The {n} item{'s' if n != 1 else ''} up top {'are' if n != 1 else 'is'} tied to California probate "
            "deadlines — those are the ones to handle before anything else, since missing them can create "
            "personal liability for you as executor. You don't have to do it all today; just start at the top."
        )
    else:
        lines.append(
            "Nothing is at risk of slipping this week, which is exactly where you want to be. "
            "Take the time you need."
        )
    lines.append("")
    lines.append("I'll check back in next Monday — and you can pull an up-to-date summary anytime from the app.")
    lines += ["", SIGNATURE, "", FOOTER]
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
