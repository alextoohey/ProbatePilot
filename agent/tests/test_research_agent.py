from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from researcher.research_agent import NewsItem, build_research_queries, run_research_agent, should_wake
from seed.demo_estate import build_demo_estate
from store.redis_client import get_estate_state, set_estate_state, set_research_run_state


def test_build_research_queries_include_state_and_county() -> None:
    estate = build_demo_estate()
    estate.county = "Alameda"

    queries = build_research_queries(estate)

    assert any("California Alameda County probate court" in query for query in queries)
    assert any("creditor notice" in query for query in queries)
    assert any("DE-160" in query for query in queries)


def test_should_wake_after_weekly_interval() -> None:
    now = datetime(2026, 6, 21, tzinfo=timezone.utc)

    assert should_wake(None, now)
    assert not should_wake((now - timedelta(days=6, hours=23)).isoformat(), now)
    assert should_wake((now - timedelta(days=7)).isoformat(), now)


def test_research_agent_skips_when_estate_checked_this_week(monkeypatch) -> None:
    monkeypatch.setenv("STORE_BACKEND", "memory")
    estate = build_demo_estate()
    set_estate_state(estate)
    now = datetime(2026, 6, 21, tzinfo=timezone.utc)
    set_research_run_state(estate.id, {"lastCheckedAt": (now - timedelta(days=1)).isoformat()})

    result = asyncio.run(run_research_agent(estate.id, now=now, fetch_news=lambda _queries, _estate: []))

    assert result.woke is False
    assert result.skippedReason


def test_research_agent_creates_attorney_review_alert(monkeypatch) -> None:
    monkeypatch.setenv("STORE_BACKEND", "memory")
    estate = build_demo_estate()
    set_estate_state(estate)
    set_research_run_state(estate.id, {})
    now = datetime(2026, 6, 21, tzinfo=timezone.utc)

    def fake_news(_queries, _estate):
        return [
            NewsItem(
                title="California probate court updates DE-160 inventory deadline requirement",
                url="https://example.test/probate-update",
                source="Example Legal News",
                publishedAt="2026-06-20T12:00:00+00:00",
                summary="A new effective rule changes inventory and appraisal requirements for executors.",
            )
        ]

    result = asyncio.run(run_research_agent(estate.id, now=now, fetch_news=fake_news))
    updated = get_estate_state(estate.id)

    assert result.woke is True
    assert len(result.findings) == 1
    assert len(result.alerts) == 1
    assert result.alerts[0].severity == "warning"
    assert "attorney's input" in result.alerts[0].actionRequired
    assert result.alerts[0].id in {alert.id for alert in updated.alerts}
