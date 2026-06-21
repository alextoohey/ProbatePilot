from __future__ import annotations

from dataclasses import asdict
from datetime import date
from email.mime import text
import json
import logging
import os
import re
from typing import Any

from llm.claude import REASONING_MODEL, create_reasoning_message
from observability.arize import set_span_attribute, set_span_error, span
from pydantic import ValidationError
from rules.california_probate import CALIFORNIA_PROBATE_RULES, RULES_BY_ID, evaluate_rules
from schemas.estate import Alert, EstateState
from store.redis_client import get_estate_state, write_alerts


LOGGER = logging.getLogger(__name__)
REQUIRED_DEMO_ALERT_IDS = {"alert-creditor-notice", "alert-de-160-inventory"}
MAX_TOOL_ROUNDS = 5
DEADLINE_AGENT_MAX_TOKENS = 8192
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
CONCRETE_TYPE_RANK = {"deadline": 0, "liability": 0, "rule_violation": 1, "missing_doc": 2}


DEADLINE_AGENT_SYSTEM_PROMPT = """
You are Executor AI's DeadlineAgent for California probate.

Use tools before finalizing. Identify operational deadline and liability risks, not legal advice.
Rank alerts by severity, urgency, and executor liability. Preserve stable alert ids from tool outputs.

Cross-rule consequences matter:
- Missing appraisals can block DE-160 Inventory & Appraisal.
- Distributions before creditor notice or claim-period close can create executor liability.

Avoid duplicate alerts for the same operational issue.
Final response:  must be a single JSON object: {"alerts": [...]}, top 5 alerts, existing Alert schema exactly.
""".strip()


DEADLINE_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_estate_summary",
        "description": "Read a compact, JSON-serializable summary of the estate state.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_california_probate_rules",
        "description": "List the deterministic California probate rules available to evaluate.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "evaluate_all_probate_rules",
        "description": "Run all deterministic California probate rules against the estate.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "evaluate_probate_rule",
        "description": "Run one deterministic California probate rule by rule id.",
        "input_schema": {
            "type": "object",
            "properties": {"rule_id": {"type": "string"}},
            "required": ["rule_id"],
            "additionalProperties": False,
        },
    },
]


async def run_deadline_agent(estate_id: str = "demo-milligan") -> list[Alert]:
    """Run Claude DeadlineAgent with deterministic rule fallback."""
    estate = get_estate_state(estate_id)
    deterministic_alerts = rank_alerts(evaluate_rules(estate))
    fallback_used = False
    fallback_reason = ""
    claude_tool_calls = 0

    with span(
        "deadline_agent.run",
        estate_id=estate_id,
        action_type="deadline_agent_run",
        rules_checked=len(CALIFORNIA_PROBATE_RULES),
        llm_model=REASONING_MODEL,
    ) as current_span:
        try:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise MissingAnthropicKeyError("ANTHROPIC_API_KEY is not set.")
            claude_result = await _run_claude_tool_loop(estate, deterministic_alerts)
            claude_tool_calls = claude_result.tool_calls
            _validated_claude_alerts_or_raise(claude_result.alerts, deterministic_alerts)
            final_alerts = deterministic_alerts
            set_span_attribute(current_span, "canonical_alert_source", "deterministic_rules")
        except Exception as exc:
            fallback_used = True
            fallback_reason = _fallback_reason(exc)
            if isinstance(exc, MissingAnthropicKeyError):
                LOGGER.info("DeadlineAgent using deterministic fallback: %s", fallback_reason)
            else:
                LOGGER.warning("DeadlineAgent using deterministic fallback: %s", fallback_reason, exc_info=True)
            final_alerts = deterministic_alerts

        final_alerts = rank_alerts(dedupe_alerts(final_alerts))
        set_span_attribute(current_span, "rules_checked", len(CALIFORNIA_PROBATE_RULES))
        set_span_attribute(current_span, "alerts_fired", len(final_alerts))
        set_span_attribute(current_span, "fallback_used", fallback_used)
        set_span_attribute(current_span, "fallback_reason", fallback_reason)
        set_span_attribute(current_span, "claude_tool_calls", claude_tool_calls)
        return write_alerts(estate_id, final_alerts)


class MissingAnthropicKeyError(RuntimeError):
    pass


class ClaudeToolUseRequiredError(RuntimeError):
    pass


class ClaudeAgentResult:
    def __init__(self, alerts: list[Alert], tool_calls: int) -> None:
        self.alerts = alerts
        self.tool_calls = tool_calls


async def _run_claude_tool_loop(estate: EstateState, deterministic_alerts: list[Alert]) -> ClaudeAgentResult:
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": _build_user_prompt(estate, deterministic_alerts),
        }
    ]
    tool_call_count = 0
    final_json_nudge_sent = False

    for _ in range(MAX_TOOL_ROUNDS):
        response = await create_reasoning_message(
            system=DEADLINE_AGENT_SYSTEM_PROMPT,
            messages=messages,
            tools=DEADLINE_AGENT_TOOLS,
            max_tokens=DEADLINE_AGENT_MAX_TOKENS,
        )
        blocks = [_content_block_to_dict(block) for block in getattr(response, "content", [])]
        messages.append({"role": "assistant", "content": blocks})

        tool_uses = [block for block in blocks if block.get("type") == "tool_use"]
        if not tool_uses:
            if tool_call_count == 0:
                raise ClaudeToolUseRequiredError("Claude returned final alerts before using any tools.")
            text = _message_text(blocks)

            LOGGER.debug("CLAUDE FINAL BLOCKS: %s", json.dumps(blocks, indent=2, default=str))
            LOGGER.debug("CLAUDE FINAL TEXT: %r", text)

            return ClaudeAgentResult(alerts=_parse_alerts_from_text(text), tool_calls=tool_call_count)

        tool_results = []
        for tool_use in tool_uses:
            tool_call_count += 1
            tool_name = str(tool_use.get("name", ""))
            tool_input = tool_use.get("input") or {}
            result = _run_deadline_agent_tool(tool_name, tool_input, estate)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use["id"],
                    "content": json.dumps(result, sort_keys=True),
                }
            )
        messages.append({"role": "user", "content": tool_results})

        if not final_json_nudge_sent:
            messages.append({
                "role": "user",
                "content": (
                    "Return the top 5 alerts as JSON only. "
                    "Use the existing Alert schema exactly. "
                    "Do not add new fields. Keep body concise."
                ),
            })
            final_json_nudge_sent = True

    raise RuntimeError("Claude DeadlineAgent exceeded max tool rounds.")


def _run_deadline_agent_tool(name: str, input_data: dict[str, Any], estate: EstateState) -> dict[str, Any]:
    with span(
        f"deadline_agent.tool.{name or 'unknown'}",
        estate_id=estate.id,
        action_type="deadline_agent_run",
        tool_name=name,
        tool_input=input_data,
    ) as tool_span:
        try:
            result = handle_deadline_agent_tool(name=name, input_data=input_data, estate=estate)
            set_span_attribute(tool_span, "tool_output_count", _tool_output_count(result))
            set_span_attribute(tool_span, "error", bool(result.get("error")))
            if result.get("error"):
                set_span_attribute(tool_span, "error.message", result.get("error"))
            return result
        except Exception as exc:
            set_span_error(tool_span, exc)
            raise


def handle_deadline_agent_tool(name: str, input_data: dict[str, Any], estate: EstateState) -> dict[str, Any]:
    if name == "get_estate_summary":
        return {"estate": estate_summary(estate)}
    if name == "list_california_probate_rules":
        return {"rules": [asdict(rule) for rule in CALIFORNIA_PROBATE_RULES]}
    if name == "evaluate_all_probate_rules":
        return {"alerts": [alert.model_dump(mode="json") for alert in evaluate_rules(estate)]}
    if name == "evaluate_probate_rule":
        rule_id = str(input_data.get("rule_id", ""))
        return evaluate_single_probate_rule_tool(estate, rule_id)
    return {"error": f"Unknown tool: {name}"}


def _tool_output_count(result: dict[str, Any]) -> int:
    if "alerts" in result and isinstance(result["alerts"], list):
        return len(result["alerts"])
    if "rules" in result and isinstance(result["rules"], list):
        return len(result["rules"])
    if "estate" in result:
        return 1
    return 0


def evaluate_single_probate_rule_tool(estate: EstateState, rule_id: str) -> dict[str, Any]:
    if rule_id not in RULES_BY_ID:
        return {"error": f"Unknown probate rule id: {rule_id}", "knownRuleIds": sorted(RULES_BY_ID)}

    matching_alerts = [
        alert.model_dump(mode="json")
        for alert in evaluate_rules(estate)
        if alert.rule.startswith(f"{rule_id}:") or alert.id.startswith(f"alert-{rule_id}")
    ]
    return {"ruleId": rule_id, "alerts": matching_alerts}


def estate_summary(estate: EstateState) -> dict[str, Any]:
    return {
        "id": estate.id,
        "deceasedName": estate.deceasedName,
        "dateOfDeath": estate.dateOfDeath,
        "appointmentDate": estate.appointmentDate,
        "state": estate.state,
        "phase": estate.phase,
        "executor": estate.executor.model_dump(mode="json"),
        "assets": [asset.model_dump(mode="json") for asset in estate.assets],
        "debts": [debt.model_dump(mode="json") for debt in estate.debts],
        "beneficiariesCount": len(estate.beneficiaries),
        "documents": [document.model_dump(mode="json") for document in estate.documents],
        "tasks": [task.model_dump(mode="json") for task in estate.tasks],
        "existingAlerts": [alert.model_dump(mode="json") for alert in estate.alerts],
    }


def rank_alerts(alerts: list[Alert]) -> list[Alert]:
    return sorted(alerts, key=_alert_sort_key)


def dedupe_alerts(alerts: list[Alert]) -> list[Alert]:
    by_id: dict[str, Alert] = {}
    for alert in alerts:
        existing = by_id.get(alert.id)
        if existing is None or _alert_sort_key(alert) < _alert_sort_key(existing):
            by_id[alert.id] = alert
    return list(by_id.values())


def _validated_claude_alerts_or_raise(claude_alerts: list[Alert], deterministic_alerts: list[Alert]) -> list[Alert]:
    alerts = rank_alerts(dedupe_alerts(claude_alerts))
    if not alerts:
        raise ValueError("Claude returned no usable alerts.")

    deterministic_ids = {alert.id for alert in deterministic_alerts}
    required_ids_present = REQUIRED_DEMO_ALERT_IDS & deterministic_ids
    claude_ids = {alert.id for alert in alerts}
    if not required_ids_present.issubset(claude_ids):
        raise ValueError("Claude dropped required deterministic demo critical alerts.")
    return alerts


def _parse_alerts_from_text(text: str) -> list[Alert]:
    last_error: Exception | None = None
    for candidate in _json_candidates(text):
        try:
            payload = json.loads(candidate)
            raw_alerts = payload.get("alerts") if isinstance(payload, dict) else payload
            if not isinstance(raw_alerts, list):
                continue

            alerts: list[Alert] = []
            for raw_alert in raw_alerts:
                alerts.append(Alert.model_validate(raw_alert))
            return alerts
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            last_error = exc

    if last_error is not None:
        raise ValueError("Claude response did not contain usable Alert JSON.") from last_error
    raise ValueError("Claude response did not contain JSON.")


def _extract_json(text: str) -> str:
    for candidate in _json_candidates(text):
        return candidate
    raise ValueError("Claude response did not contain JSON.")


def _json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    for fenced in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL):
        _append_json_candidates(fenced, candidates, seen)

    _append_json_candidates(text, candidates, seen)
    return candidates


def _append_json_candidates(source: str, candidates: list[str], seen: set[str]) -> None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(source):
        if char not in "{[":
            continue
        try:
            _, end = decoder.raw_decode(source[index:])
        except json.JSONDecodeError:
            continue

        candidate = source[index : index + end].strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)


def _build_user_prompt(estate: EstateState, deterministic_alerts: list[Alert]) -> str:
    return (
        "Evaluate this estate and return ranked alerts.\n\n"
        f"Estate summary:\n{json.dumps(estate_summary(estate), sort_keys=True)}\n\n"
        "Deterministic rule output is available through tools. The current deterministic "
        "alerts are included so you can preserve stable ids while reasoning about priority:\n"
        f"{json.dumps([alert.model_dump(mode='json') for alert in deterministic_alerts], sort_keys=True)}"
    )


def _content_block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if hasattr(block, "dict"):
        return block.dict()
    return {"type": getattr(block, "type", "text"), "text": str(block)}


def _message_text(blocks: list[dict[str, Any]]) -> str:
    return "\n".join(str(block.get("text", "")) for block in blocks if block.get("type") == "text")


def _alert_sort_key(alert: Alert) -> tuple[int, int, int, str]:
    days_remaining = 999999 if alert.daysRemaining is None else alert.daysRemaining
    return (
        SEVERITY_RANK[alert.severity],
        CONCRETE_TYPE_RANK[alert.type],
        days_remaining,
        alert.id,
    )


def _fallback_reason(exc: Exception) -> str:
    if isinstance(exc, MissingAnthropicKeyError):
        return "missing_anthropic_api_key"
    if isinstance(exc, ClaudeToolUseRequiredError):
        return "claude_returned_without_tool_use"
    return f"{exc.__class__.__name__}: {str(exc)[:160]}"
