from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace

from agents import deadline_agent
from agents.deadline_agent import (
    _extract_json,
    _parse_alerts_from_text,
    handle_deadline_agent_tool,
    mark_alert_complete,
    refresh_deadline_state,
    run_deadline_agent,
)
from schemas.estate import Task
from seed.demo_estate import build_demo_estate
from store.redis_client import get_alerts, get_estate_state, seed_demo_estate


class CapturedSpan:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = dict(attributes)

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


def capture_deadline_agent_spans(monkeypatch) -> list[CapturedSpan]:
    captured: list[CapturedSpan] = []

    @contextmanager
    def fake_span(name: str, **attributes: object):
        span = CapturedSpan(attributes)
        captured.append(span)
        yield span

    monkeypatch.setattr(deadline_agent, "span", fake_span)
    return captured


def deterministic_alert_payload() -> dict[str, object]:
    return handle_deadline_agent_tool(
        name="evaluate_all_probate_rules",
        input_data={},
        estate=build_demo_estate(),
    )


def deterministic_alert_json() -> str:
    return json.dumps(deterministic_alert_payload())


def test_fallback_returns_required_demo_critical_alerts(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    alert_ids = {alert.id for alert in alerts}

    assert "alert-creditor-notice" in alert_ids
    assert "alert-de-160-inventory" in alert_ids


def test_alert_ranking_puts_critical_alerts_first(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))

    assert alerts[0].id == "alert-creditor-notice"
    assert alerts[0].severity == "critical"
    assert alerts[0].timingStatus == "dated"
    # state-agency-notice is also critical/liability-typed, and outranks the
    # deadline-typed de-160 alert in TYPE_RANK regardless of days remaining.
    assert alerts[1].id == "alert-state-agency-notice"
    assert alerts[1].severity == "critical"
    assert isinstance(alerts[1].daysRemaining, int)
    assert alerts[2].id == "alert-de-160-inventory"
    assert alerts[2].severity == "critical"
    assert isinstance(alerts[2].daysRemaining, int)


def test_deterministic_alerts_assign_timing_status() -> None:
    from datetime import date

    from rules.california_probate import evaluate_rules

    estate = build_demo_estate()
    next(task for task in estate.tasks if task.id == "task-obtain-ein").status = "todo"
    alerts = {alert.id: alert for alert in evaluate_rules(estate, today=date(2026, 6, 21))}

    assert alerts["alert-creditor-notice"].timingStatus == "dated"
    assert alerts["alert-de-160-inventory"].timingStatus == "dated"
    assert alerts["alert-estate-ein"].timingStatus == "prerequisite"
    assert alerts["alert-estate-ein"].severity == "warning"


def test_malformed_claude_output_falls_back_safely(monkeypatch) -> None:
    responses = [
        SimpleNamespace(
            content=[
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "evaluate_all_probate_rules",
                    "input": {},
                }
            ]
        ),
        SimpleNamespace(content=[{"type": "text", "text": "not json"}]),
    ]

    async def malformed_message(**kwargs):
        return responses.pop(0)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(deadline_agent, "create_reasoning_message", malformed_message)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    alert_ids = {alert.id for alert in alerts}

    assert "alert-creditor-notice" in alert_ids
    assert "alert-de-160-inventory" in alert_ids


def test_malformed_claude_json_is_repaired_with_forced_submission_tool(monkeypatch) -> None:
    captured = capture_deadline_agent_spans(monkeypatch)
    payload = deterministic_alert_payload()
    requests: list[dict[str, object]] = []
    responses = [
        SimpleNamespace(
            content=[
                {
                    "type": "tool_use",
                    "id": "toolu_rules",
                    "name": "evaluate_all_probate_rules",
                    "input": {},
                }
            ]
        ),
        SimpleNamespace(
            stop_reason="max_tokens",
            content=[
                {
                    "type": "text",
                    "text": '{"alerts":[{"steps":["Go to irs.gov and apply for an EIN"]}',
                }
            ],
        ),
        SimpleNamespace(
            content=[
                {
                    "type": "tool_use",
                    "id": "toolu_submit",
                    "name": "submit_deadline_alerts",
                    "input": payload,
                }
            ]
        ),
    ]

    async def tool_then_repaired_message(**kwargs):
        requests.append(kwargs)
        return responses.pop(0)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(deadline_agent, "create_reasoning_message", tool_then_repaired_message)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))

    assert "alert-creditor-notice" in {alert.id for alert in alerts}
    assert requests[-1]["tool_choice"] == {"type": "tool", "name": "submit_deadline_alerts"}
    assert requests[-1]["max_tokens"] == 12288
    assert captured[0].attributes["fallback_used"] is False
    assert captured[0].attributes["claude_tool_calls"] == 2
    assert captured[0].attributes["json_repair_used"] is True


def test_parse_alerts_accepts_markdown_json_fence() -> None:
    text = f"```json\n{deterministic_alert_json()}\n```"

    alerts = _parse_alerts_from_text(text)

    assert "alert-creditor-notice" in {alert.id for alert in alerts}
    assert _extract_json(text).startswith('{"alerts"')


def test_parse_alerts_accepts_explanatory_text_and_trailing_text() -> None:
    text = f"Here are the ranked alerts:\n{deterministic_alert_json()}\nUse these in the dashboard."

    alerts = _parse_alerts_from_text(text)

    assert "alert-de-160-inventory" in {alert.id for alert in alerts}


def test_parse_alerts_skips_partial_json_before_final_payload() -> None:
    text = (
        'Tool output started: {"alerts": [{"id": "partial-alert", "severity": "critical"}]\n'
        "Final answer:\n"
        f"{deterministic_alert_json()}\n"
        "Done."
    )

    alerts = _parse_alerts_from_text(text)

    assert "alert-creditor-notice" in {alert.id for alert in alerts}


def test_parse_alerts_accepts_bare_alert_array() -> None:
    payload = deterministic_alert_payload()
    text = "```json\n" + json.dumps(payload["alerts"]) + "\n```\nTrailing note."

    alerts = _parse_alerts_from_text(text)

    assert "alert-de-160-inventory" in {alert.id for alert in alerts}


def test_valid_claude_json_without_tool_call_falls_back(monkeypatch) -> None:
    captured = capture_deadline_agent_spans(monkeypatch)

    async def no_tool_message(**kwargs):
        return SimpleNamespace(content=[{"type": "text", "text": json.dumps(deterministic_alert_payload())}])

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(deadline_agent, "create_reasoning_message", no_tool_message)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    alert_ids = {alert.id for alert in alerts}

    assert "alert-creditor-notice" in alert_ids
    assert "alert-de-160-inventory" in alert_ids
    assert captured[-1].attributes["fallback_used"] is True
    assert captured[-1].attributes["fallback_reason"] == "claude_returned_without_tool_use"
    assert captured[-1].attributes["claude_tool_calls"] == 0


def test_claude_path_with_tool_call_and_valid_final_json_is_accepted(monkeypatch) -> None:
    captured = capture_deadline_agent_spans(monkeypatch)
    responses = [
        SimpleNamespace(
            content=[
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "evaluate_all_probate_rules",
                    "input": {},
                }
            ]
        ),
        SimpleNamespace(content=[{"type": "text", "text": json.dumps(deterministic_alert_payload())}]),
    ]

    async def tool_then_json_message(**kwargs):
        return responses.pop(0)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(deadline_agent, "create_reasoning_message", tool_then_json_message)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    alert_ids = {alert.id for alert in alerts}

    assert "alert-creditor-notice" in alert_ids
    assert "alert-de-160-inventory" in alert_ids
    assert captured[0].attributes["fallback_used"] is False
    assert captured[0].attributes["fallback_reason"] == ""
    assert captured[0].attributes["claude_tool_calls"] == 1


def test_claude_can_submit_schema_without_text_json_repair(monkeypatch) -> None:
    captured = capture_deadline_agent_spans(monkeypatch)
    requests: list[dict[str, object]] = []
    responses = [
        SimpleNamespace(
            content=[{
                "type": "tool_use",
                "id": "toolu_evaluate",
                "name": "evaluate_all_probate_rules",
                "input": {},
            }]
        ),
        SimpleNamespace(
            content=[{
                "type": "tool_use",
                "id": "toolu_submit",
                "name": "submit_deadline_alerts",
                "input": deterministic_alert_payload(),
            }]
        ),
    ]

    async def tool_then_submission(**kwargs):
        requests.append(kwargs)
        return responses.pop(0)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(deadline_agent, "create_reasoning_message", tool_then_submission)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))

    assert "alert-creditor-notice" in {alert.id for alert in alerts}
    assert captured[0].attributes["fallback_used"] is False
    assert captured[0].attributes["json_repair_used"] is False
    assert captured[0].attributes["claude_tool_calls"] == 2
    assert requests[0]["tool_choice"] is None
    assert requests[1]["tool_choice"] == {"type": "tool", "name": "submit_deadline_alerts"}


def test_run_deadline_agent_writes_alerts_to_store(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    stored_alerts = get_alerts("demo-milligan")

    assert [alert.id for alert in stored_alerts] == [alert.id for alert in alerts]


def test_mark_alert_complete_dismisses_alert_and_completes_task(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()
    asyncio.run(run_deadline_agent("demo-milligan"))

    estate = mark_alert_complete("demo-milligan", "alert-creditor-notice")

    alert = next(item for item in estate.alerts if item.id == "alert-creditor-notice")
    task = next(item for item in estate.tasks if item.relatedAlertId == "alert-creditor-notice")

    assert alert.dismissed is True
    assert task.status == "done"


def test_completed_task_survives_refresh_and_alert_does_not_reappear(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()
    asyncio.run(run_deadline_agent("demo-milligan"))
    mark_alert_complete("demo-milligan", "alert-creditor-notice")

    alerts = refresh_deadline_state("demo-milligan")
    estate = get_estate_state("demo-milligan")

    task = next(item for item in estate.tasks if item.relatedAlertId == "alert-creditor-notice")

    assert "alert-creditor-notice" not in {item.id for item in alerts}
    assert task.status == "done"
    assert "alert-debt-resolution" in {item.id for item in alerts}


def test_complete_alert_route_does_not_wait_for_claude(monkeypatch) -> None:
    from api.routers import agents as agents_router
    from schemas.api import CompleteAlertRequest

    seed_demo_estate()
    refresh_deadline_state("demo-milligan")

    async def unexpected_claude_run(*args, **kwargs):
        raise AssertionError("complete-alert must not wait for Claude")

    monkeypatch.setattr(agents_router, "run_deadline_agent", unexpected_claude_run)
    response = asyncio.run(agents_router.complete_alert(
        CompleteAlertRequest(estateId="demo-milligan", alertId="alert-creditor-notice"),
        user=None,
    ))

    alert_ids = {alert.id for alert in response.estate.alerts}
    assert "alert-creditor-notice" not in alert_ids
    assert "alert-debt-resolution" in alert_ids


def test_deterministic_tasks_unlock_from_stable_completed_ids() -> None:
    from datetime import date

    from rules.california_probate import evaluate_rules

    estate = build_demo_estate()
    estate.documents = [document for document in estate.documents if document.documentType != "letters_testamentary"]
    estate.tasks = []

    initial_ids = {alert.id for alert in evaluate_rules(estate, today=date(2026, 6, 21))}
    assert "alert-de-140-petition" in initial_ids
    assert "alert-letters-testamentary" not in initial_ids
    assert "alert-estate-ein" not in initial_ids

    estate.tasks.append(Task(
        id="task-de-140-petition",
        title="File the probate petition",
        status="done",
        phase=1,
        relatedAlertId="alert-de-140-petition",
    ))
    petition_complete_ids = {alert.id for alert in evaluate_rules(estate, today=date(2026, 6, 21))}
    assert "alert-de-140-petition" not in petition_complete_ids
    assert "alert-letters-testamentary" in petition_complete_ids
    assert "alert-estate-ein" not in petition_complete_ids

    estate.tasks.append(Task(
        id="task-letters-testamentary",
        title="Upload Letters Testamentary",
        status="done",
        phase=1,
        relatedAlertId="alert-letters-testamentary",
    ))
    authority_ids = {alert.id for alert in evaluate_rules(estate, today=date(2026, 6, 21))}
    assert "alert-letters-testamentary" not in authority_ids
    assert "alert-estate-ein" in authority_ids
    assert "alert-de-160-inventory" in authority_ids
    assert "alert-creditor-notice" in authority_ids
    assert "alert-estate-bank-account" not in authority_ids

    estate.tasks.append(Task(
        id="task-estate-ein",
        title="Obtain estate EIN",
        status="done",
        phase=2,
        relatedAlertId="alert-estate-ein",
    ))
    ein_ids = {alert.id for alert in evaluate_rules(estate, today=date(2026, 6, 21))}
    assert "alert-estate-ein" not in ein_ids
    assert "alert-estate-bank-account" in ein_ids


def test_evaluate_all_rules_tool_returns_json_serializable_alert_data() -> None:
    result = handle_deadline_agent_tool(
        name="evaluate_all_probate_rules",
        input_data={},
        estate=build_demo_estate(),
    )

    assert "alerts" in result
    assert "alert-creditor-notice" in {alert["id"] for alert in result["alerts"]}
    json.dumps(result, sort_keys=True)
