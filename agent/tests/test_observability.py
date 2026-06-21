from __future__ import annotations

import asyncio
from contextlib import contextmanager

from fastapi.testclient import TestClient

from agents import deadline_agent
from agents.deadline_agent import run_deadline_agent
import main
from observability import phoenix
from store.redis_client import seed_demo_estate


class CapturedSpan:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = dict(attributes)

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.attributes["recorded_exception"] = exc.__class__.__name__


def test_init_tracing_registers_phoenix_and_both_llm_instrumentors(monkeypatch) -> None:
    register_args: dict[str, object] = {}
    instrumentation_calls: list[object] = []

    class FakeProvider:
        def get_tracer(self, name: str) -> object:
            register_args["tracer_name"] = name
            return object()

    class FakeInstrumentor:
        def instrument(self, **kwargs: object) -> None:
            instrumentation_calls.append(kwargs["tracer_provider"])

    def fake_register(**kwargs: object) -> FakeProvider:
        register_args.update(kwargs)
        return FakeProvider()

    monkeypatch.setattr(phoenix, "_INITIALIZED", False)
    monkeypatch.setattr(phoenix, "_TRACING_ENABLED", False)
    monkeypatch.setattr(phoenix, "_TRACER", None)
    monkeypatch.setattr(phoenix, "phoenix_register", fake_register)
    monkeypatch.setattr(phoenix, "AnthropicInstrumentor", FakeInstrumentor)
    monkeypatch.setattr(phoenix, "OpenAIInstrumentor", FakeInstrumentor)
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix:6006/v1/traces")
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "executor-ai-test")

    phoenix.init_tracing()

    assert register_args["endpoint"] == "http://phoenix:6006/v1/traces"
    assert register_args["project_name"] == "executor-ai-test"
    assert register_args["protocol"] == "http/protobuf"
    assert register_args["tracer_name"] == "executor-ai.agent"
    assert len(instrumentation_calls) == 2
    assert phoenix.get_tracing_status()["provider"] == "phoenix"


def test_span_noop_mode_yields_span_like_object(monkeypatch) -> None:
    monkeypatch.setattr(phoenix, "_INITIALIZED", True)
    monkeypatch.setattr(phoenix, "_TRACING_ENABLED", False)
    monkeypatch.setattr(phoenix, "_TRACER", None)

    with phoenix.span("test.noop") as current_span:
        current_span.set_attribute("demo", "ok")
        current_span.record_exception(RuntimeError("ignored"))


def test_deadline_agent_fallback_works_when_tracing_disabled(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(phoenix, "_INITIALIZED", True)
    monkeypatch.setattr(phoenix, "_TRACING_ENABLED", False)
    monkeypatch.setattr(phoenix, "_TRACER", None)
    seed_demo_estate()

    alerts = asyncio.run(run_deadline_agent("demo-milligan"))
    alert_ids = {alert.id for alert in alerts}

    assert "alert-creditor-notice" in alert_ids
    assert "alert-de-160-inventory" in alert_ids


def test_deadline_agent_fallback_attributes_can_be_set(monkeypatch) -> None:
    captured: list[CapturedSpan] = []

    @contextmanager
    def fake_span(name: str, **attributes: object):
        current_span = CapturedSpan(attributes)
        captured.append(current_span)
        yield current_span

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(deadline_agent, "span", fake_span)
    seed_demo_estate()

    asyncio.run(run_deadline_agent("demo-milligan"))

    assert captured[-1].attributes["fallback_used"] is True
    assert captured[-1].attributes["fallback_reason"] == "missing_anthropic_api_key"
    assert captured[-1].attributes["claude_tool_calls"] == 0
    assert captured[-1].attributes["alerts_fired"] >= 2


def test_chat_still_streams_when_retrieval_fails(monkeypatch) -> None:
    seed_demo_estate()

    def failing_embed_query(message: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(main, "embed_query", failing_embed_query)
    client = TestClient(main.app)

    response = client.post(
        "/chat",
        json={"estateId": "demo-milligan", "message": "What should I do next?", "topK": 3},
    )

    assert response.status_code == 200
    assert 'data: {"token":' in response.text
    assert "data: [DONE]" in response.text


def test_generate_letter_still_works_without_anthropic_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seed_demo_estate()
    client = TestClient(main.app)

    response = client.post(
        "/generate-letter",
        json={
            "estateId": "demo-milligan",
            "letterType": "creditor_notice",
            "recipientName": "UCSF Medical Center",
        },
    )

    assert response.status_code == 200
    assert "California Probate Code §9051" in response.json()["draft"]
