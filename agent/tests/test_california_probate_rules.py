from __future__ import annotations

from datetime import date

from rules.california_probate import evaluate_rules
from seed.demo_estate import build_demo_estate


DEMO_TODAY = date(2026, 6, 20)


def test_demo_estate_includes_required_critical_alerts() -> None:
    alerts = evaluate_rules(build_demo_estate(), today=DEMO_TODAY)
    alerts_by_id = {alert.id: alert for alert in alerts}

    de_160 = alerts_by_id["alert-de-160-inventory"]
    assert de_160.severity == "critical"
    assert de_160.type == "deadline"
    assert "DE-160 Inventory & Appraisal is blocked" == de_160.title
    assert "Appraisals are missing for" in de_160.body
    assert "1847 Marin Ave" in de_160.body
    assert "2019 Honda Civic" in de_160.body

    creditor_notice = alerts_by_id["alert-creditor-notice"]
    assert creditor_notice.severity == "critical"
    assert creditor_notice.type == "liability"
    assert creditor_notice.title == "Known creditors have not been notified"
    assert "Unnotified creditors" in creditor_notice.body
    assert "UCSF Medical Center" in creditor_notice.body
    assert "First Republic Mortgage" in creditor_notice.body


def test_missing_or_invalid_required_data_returns_alerts_without_crashing() -> None:
    estate = build_demo_estate().model_copy(update={"appointmentDate": ""})

    alerts = evaluate_rules(estate, today=DEMO_TODAY)

    assert any(alert.id == "alert-de-160-missing-appointmentdate" for alert in alerts)
    assert any(alert.id == "alert-creditor-notice-missing-appointmentdate" for alert in alerts)
    assert all(alert.title for alert in alerts)


def test_alert_output_is_stable_across_repeated_calls() -> None:
    estate = build_demo_estate()

    first = [alert.model_dump() for alert in evaluate_rules(estate, today=DEMO_TODAY)]
    second = [alert.model_dump() for alert in evaluate_rules(estate, today=DEMO_TODAY)]

    assert first == second
