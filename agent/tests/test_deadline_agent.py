from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace

from agents import deadline_agent
from agents.deadline_agent import _extract_json, _parse_alerts_from_text, handle_deadline_agent_tool, mark_alert_complete, run_deadline_agent
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

    assert alerts[0].id == "alert-de-140-petition"
    assert alerts[0].severity == "critical"
    assert alerts[0].timingStatus == "blocking"
    assert alerts[1].id == "alert-creditor-notice"
    assert alerts[1].severity == "critical"
    assert isinstance(alerts[1].daysRemaining, int)
    assert alerts[2].id == "alert-de-160-inventory"
    assert alerts[2].severity == "critical"


def test_deterministic_alerts_assign_timing_status() -> None:
    from datetime import date
    from rules.california_probate import evaluate_rules

    alerts = {alert.id: alert for alert in evaluate_rules(build_demo_estate(), today=date(2026, 6, 21))}

    assert alerts["alert-de-140-petition"].timingStatus == "blocking"
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


def test_completed_alert_and_task_survive_deadline_agent_refresh(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()
    asyncio.run(run_deadline_agent("demo-milligan"))
    mark_alert_complete("demo-milligan", "alert-creditor-notice")

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    estate = get_estate_state("demo-milligan")

    alert = next(item for item in alerts if item.id == "alert-creditor-notice")
    task = next(item for item in estate.tasks if item.relatedAlertId == "alert-creditor-notice")

    assert alert.dismissed is True
    assert task.status == "done"


def test_evaluate_all_rules_tool_returns_json_serializable_alert_data() -> None:
    result = handle_deadline_agent_tool(
        name="evaluate_all_probate_rules",
        input_data={},
        estate=build_demo_estate(),
    )

    assert "alerts" in result
    assert "alert-creditor-notice" in {alert["id"] for alert in result["alerts"]}
    json.dumps(result, sort_keys=True)
