from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = REPO_ROOT / "agent"

if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


@pytest.fixture(autouse=True)
def memory_store(monkeypatch: pytest.MonkeyPatch):
    """Keep tests isolated from Redis Cloud and from each other."""
    monkeypatch.setenv("STORE_BACKEND", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    monkeypatch.delenv("UPSTASH_VECTOR_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_VECTOR_REST_TOKEN", raising=False)

    from store import redis_client

    redis_client._ESTATES.clear()
    redis_client._VECTORS.clear()
    redis_client._REDIS_CLIENT = None
    redis_client._REDIS_CLOUD_CLIENT = None
    redis_client._VECTOR_CLIENT = None

    yield

    redis_client._ESTATES.clear()
    redis_client._VECTORS.clear()
