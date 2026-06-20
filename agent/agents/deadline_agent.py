from __future__ import annotations

from observability.phoenix import span
from rules.california_probate import CALIFORNIA_PROBATE_RULES, evaluate_rules
from schemas.estate import Alert
from store.redis_client import get_estate_state, write_alerts


async def run_deadline_agent(estate_id: str = "demo-milligan") -> list[Alert]:
    """Deterministic placeholder for the future Claude tool-use DeadlineAgent."""
    with span(
        "deadline_agent.run",
        estate_id=estate_id,
        action_type="deadline_agent_run",
        rules_checked=len(CALIFORNIA_PROBATE_RULES),
    ):
        estate = get_estate_state(estate_id)
        alerts = evaluate_rules(estate)
        return write_alerts(estate_id, alerts)

