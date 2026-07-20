from __future__ import annotations

import sys
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


@pytest.fixture(autouse=True)
def memory_store(monkeypatch: pytest.MonkeyPatch):
    """Keep tests hermetic: in-memory store, no live LLM/embedding/tracing
    calls leaking in from a real .env. Mirrors tests/conftest.py — this
    directory has its own conftest because it sits outside the top-level
    tests/ tree pytest normally discovers fixtures from."""
    monkeypatch.setenv("STORE_BACKEND", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    monkeypatch.delenv("UPSTASH_VECTOR_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_VECTOR_REST_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)

    from observability import phoenix
    from store import redis_client

    # Tests that call a real, unmocked route (TestClient) would otherwise hit
    # observability.phoenix.span()'s lazy init_tracing() and attempt a live
    # connection to a Phoenix collector. Treat tracing as already initialized
    # (and disabled) by default; tests that exercise init_tracing() itself
    # override these with their own monkeypatch.setattr calls.
    monkeypatch.setattr(phoenix, "_INITIALIZED", True)
    monkeypatch.setattr(phoenix, "_TRACING_ENABLED", False)
    monkeypatch.setattr(phoenix, "_TRACER", None)

    redis_client.reset_state()
    yield
    redis_client.reset_state()
