from __future__ import annotations

import hashlib
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import Field

from observability.phoenix import set_span_attribute, span
from schemas.estate import Alert, ContractModel, EstateState
from store.redis_client import (
    DEFAULT_ESTATE_ID,
    get_estate_state,
    get_research_run_state,
    list_estate_ids,
    set_estate_state,
    set_research_run_state,
)

# This module searches Google News RSS and keyword-matches for relevance — an
# unofficial source with no real judgment behind it (no LLM call anywhere in
# here despite the name). It's also not wired to anything: no frontend
# trigger, no scheduler. A better, source-verified redesign (poll the actual
# CA statute/form pages this app's rules already cite, diff their amendment
# dates, and use Claude only once a real change is confirmed) is fully scoped
# in docs/RESEARCH_AGENT_REDESIGN.md — not yet built.

LOGGER = logging.getLogger(__name__)
DEFAULT_WAKE_INTERVAL = timedelta(days=7)
DEFAULT_NEWS_ITEMS_PER_QUERY = 3
NewsFetcher = Callable[[list[str], EstateState], Iterable["NewsItem"]]

PROBATE_PROCESS_KEYWORDS = {
    "probate": "General probate process",
    "executor": "Executor duties",
    "personal representative": "Personal representative duties",
    "creditor": "Creditor notice or claims",
    "claim": "Creditor notice or claims",
    "inventory": "Inventory and appraisal",
    "appraisal": "Inventory and appraisal",
    "de-160": "Inventory and appraisal",
    "petition": "Probate petition",
    "tax": "Estate tax or final tax filing",
    "distribution": "Beneficiary distributions",
    "notice": "Required notices",
}

UPDATE_KEYWORDS = {
    "amend",
    "amended",
    "change",
    "changed",
    "deadline",
    "effective",
    "new",
    "proposed",
    "requirement",
    "rules",
    "statute",
    "update",
    "updated",
}


class NewsItem(ContractModel):
    title: str
    url: str
    source: str
    publishedAt: str | None = None
    summary: str = ""


class ResearchFinding(ContractModel):
    process: str
    title: str
    source: str
    url: str
    summary: str
    publishedAt: str | None = None
    relevance: Literal["high", "medium"] = "medium"


class ResearchAgentResult(ContractModel):
    estateId: str
    woke: bool
    checkedAt: str
    nextWakeAt: str
    queries: list[str] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    skippedReason: str | None = None


class ResearcherConfig(ContractModel):
    wakeIntervalDays: int = 7
    maxFindings: int = 5


def should_wake(last_checked_at: str | None, now: datetime | None = None, interval: timedelta = DEFAULT_WAKE_INTERVAL) -> bool:
    if not last_checked_at:
        return True
    checked_at = _parse_datetime(last_checked_at)
    if checked_at is None:
        return True
    return (_utc(now) - checked_at) >= interval


async def run_research_agent(
    estate_id: str = DEFAULT_ESTATE_ID,
    *,
    now: datetime | None = None,
    force: bool = False,
    fetch_news: NewsFetcher | None = None,
    config: ResearcherConfig | None = None,
) -> ResearchAgentResult:
    """Wake weekly to look for state probate-process updates and surface review alerts."""
    config = config or ResearcherConfig()
    now = _utc(now)
    checked_at = now.isoformat()
    interval = timedelta(days=config.wakeIntervalDays)
    run_state = get_research_run_state(estate_id)
    last_checked_at = run_state.get("lastCheckedAt")

    with span(
        "research_agent.run",
        estate_id=estate_id,
        action_type="research_agent_run",
        agent_name="ResearchAgent",
    ) as current_span:
        if not force and not should_wake(last_checked_at, now, interval):
            next_wake_at = (_parse_datetime(str(last_checked_at)) + interval).isoformat()  # type: ignore[union-attr]
            set_span_attribute(current_span, "research_agent.woke", False)
            return ResearchAgentResult(
                estateId=estate_id,
                woke=False,
                checkedAt=checked_at,
                nextWakeAt=next_wake_at,
                skippedReason="ResearchAgent already checked this estate within the weekly window.",
            )

        estate = get_estate_state(estate_id)
        queries = build_research_queries(estate)
        news_fetcher = fetch_news or fetch_google_news_rss
        raw_items = list(news_fetcher(queries, estate))
        findings = rank_findings(classify_news(raw_items), max_findings=config.maxFindings)
        alerts = merge_research_alerts(estate, findings, checked_at)
        set_research_run_state(
            estate_id,
            {
                "lastCheckedAt": checked_at,
                "nextWakeAt": (now + interval).isoformat(),
                "queryCount": len(queries),
                "findingCount": len(findings),
            },
        )
        set_span_attribute(current_span, "research_agent.woke", True)
        set_span_attribute(current_span, "research_agent.query_count", len(queries))
        set_span_attribute(current_span, "research_agent.news_items", len(raw_items))
        set_span_attribute(current_span, "research_agent.findings", len(findings))
        set_span_attribute(current_span, "research_agent.alerts_created", len(alerts))

        return ResearchAgentResult(
            estateId=estate_id,
            woke=True,
            checkedAt=checked_at,
            nextWakeAt=(now + interval).isoformat(),
            queries=queries,
            findings=findings,
            alerts=alerts,
        )


async def run_due_research_for_estates(
    estate_ids: list[str] | None = None,
    *,
    now: datetime | None = None,
    fetch_news: NewsFetcher | None = None,
    config: ResearcherConfig | None = None,
) -> list[ResearchAgentResult]:
    ids = estate_ids if estate_ids is not None else list_estate_ids()
    results: list[ResearchAgentResult] = []
    for estate_id in ids:
        try:
            results.append(
                await run_research_agent(
                    estate_id,
                    now=now,
                    fetch_news=fetch_news,
                    config=config,
                )
            )
        except KeyError:
            LOGGER.warning("ResearchAgent skipped missing estate %s.", estate_id)
    return results


def build_research_queries(estate: EstateState) -> list[str]:
    state = _state_label(estate.state)
    county = f" {estate.county} County" if estate.county else ""
    return [
        f"{state}{county} probate court deadline updates",
        f"{state} probate executor creditor notice rule update",
        f"{state} probate inventory appraisal DE-160 update",
        f"{state} estate administration court form update",
    ]


def fetch_google_news_rss(
    queries: list[str],
    estate: EstateState,
    *,
    items_per_query: int = DEFAULT_NEWS_ITEMS_PER_QUERY,
    timeout_seconds: float = 4.0,
) -> list[NewsItem]:
    del estate
    items: list[NewsItem] = []
    for query in queries:
        encoded = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        url = f"https://news.google.com/rss/search?{encoded}"
        try:
            with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
                xml_bytes = response.read()
        except Exception as exc:
            LOGGER.warning("ResearchAgent news fetch failed for query %r: %s", query, exc)
            continue
        items.extend(_news_items_from_rss(xml_bytes, items_per_query=items_per_query))
    return items


def classify_news(items: Iterable[NewsItem]) -> list[ResearchFinding]:
    findings: list[ResearchFinding] = []
    seen_urls: set[str] = set()
    for item in items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        text = f"{item.title} {item.summary}".lower()
        process = _matched_process(text)
        if process is None or not any(keyword in text for keyword in UPDATE_KEYWORDS):
            continue
        findings.append(
            ResearchFinding(
                process=process,
                title=item.title,
                source=item.source,
                url=item.url,
                summary=item.summary or "A possible probate process update was found.",
                publishedAt=item.publishedAt,
                relevance="high" if _is_high_relevance(text) else "medium",
            )
        )
    return findings


def rank_findings(findings: list[ResearchFinding], max_findings: int = 5) -> list[ResearchFinding]:
    return sorted(
        findings,
        key=lambda finding: (
            0 if finding.relevance == "high" else 1,
            finding.publishedAt or "",
            finding.title,
        ),
    )[:max_findings]


def merge_research_alerts(estate: EstateState, findings: list[ResearchFinding], checked_at: str) -> list[Alert]:
    if not findings:
        set_estate_state(estate)
        return []

    existing = {alert.id: alert for alert in estate.alerts}
    created: list[Alert] = []
    for finding in findings:
        alert = _alert_from_finding(finding, checked_at)
        existing[alert.id] = alert
        created.append(alert)
    estate.alerts = list(existing.values())
    set_estate_state(estate)
    return created


def _alert_from_finding(finding: ResearchFinding, checked_at: str) -> Alert:
    digest = hashlib.sha1(finding.url.encode("utf-8")).hexdigest()[:12]
    return Alert(
        id=f"alert-research-{digest}",
        severity="warning" if finding.relevance == "high" else "info",
        type="rule_violation",
        title=f"Possible {finding.process.lower()} update",
        body=(
            f"{finding.source} reported: {finding.title}. "
            "This may affect an estate administration process, but it needs attorney review before you act on it."
        ),
        rule="research-agent-weekly-news",
        timingStatus="no_deadline",
        actionRequired=f"This requires your attorney's input because it may affect {finding.process}.",
        whatYouNeed=[finding.url],
        steps=[
            "Open the source and save a copy for the estate file.",
            "Ask the estate attorney whether this changes your next step or deadline.",
            "Update ProbatePilot after your attorney confirms the impact.",
        ],
        createdAt=checked_at,
        dismissed=False,
    )


def _matched_process(text: str) -> str | None:
    for keyword, process in PROBATE_PROCESS_KEYWORDS.items():
        if keyword in text:
            return process
    return None


def _is_high_relevance(text: str) -> bool:
    return any(keyword in text for keyword in ("deadline", "effective", "requirement", "statute", "de-160"))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _state_label(state: str) -> str:
    return "California" if state.lower() == "california" else state.title()


def _news_items_from_rss(xml_bytes: bytes, *, items_per_query: int) -> list[NewsItem]:
    root = ET.fromstring(xml_bytes)
    parsed_items: list[NewsItem] = []
    for item in root.findall("./channel/item")[:items_per_query]:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        published_at = (item.findtext("pubDate") or "").strip() or None
        source_node = item.find("source")
        source = (source_node.text if source_node is not None and source_node.text else "Google News").strip()
        summary = (item.findtext("description") or "").strip()
        if title and url:
            parsed_items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source=source,
                    publishedAt=published_at,
                    summary=summary,
                )
            )
    return parsed_items
