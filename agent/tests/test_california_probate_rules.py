from __future__ import annotations

from datetime import date

from rules.california_probate import evaluate_rules
from schemas.estate import Debt
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


def test_debt_order_flags_unsecured_notice_ahead_of_secured() -> None:
    out_of_order = build_demo_estate().model_copy(update={
        "debts": [
            Debt(id="debt-visa", creditor="Chase Visa", amount=3100, type="unsecured", notified=True),
            Debt(id="debt-mortgage", creditor="First Republic Mortgage", amount=141000, type="secured", notified=False),
        ],
    })
    correct_order = out_of_order.model_copy(update={
        "debts": [
            Debt(id="debt-visa", creditor="Chase Visa", amount=3100, type="unsecured", notified=False),
            Debt(id="debt-mortgage", creditor="First Republic Mortgage", amount=141000, type="secured", notified=True),
        ],
    })

    out_of_order_alerts = {alert.id: alert for alert in evaluate_rules(out_of_order, today=DEMO_TODAY)}
    assert "alert-debt-order" in out_of_order_alerts
    violation = out_of_order_alerts["alert-debt-order"]
    assert violation.severity == "critical"
    assert violation.type == "rule_violation"
    assert "First Republic Mortgage" in violation.body

    assert "alert-debt-order" not in {alert.id for alert in evaluate_rules(correct_order, today=DEMO_TODAY)}


def test_state_agency_notice_fires_and_clears_once_recorded() -> None:
    estate = build_demo_estate()
    alerts = {alert.id: alert for alert in evaluate_rules(estate, today=DEMO_TODAY)}

    notice = alerts["alert-state-agency-notice"]
    assert notice.severity == "critical"
    assert notice.type == "liability"
    assert "Medi-Cal" in notice.body
    assert isinstance(notice.daysRemaining, int)

    for task in estate.tasks:
        if task.id == "task-notify-creditors":
            task.status = "done"
    from schemas.estate import Task

    estate.tasks.append(Task(id="task-state-agency-notice", title="Notify state agencies (Medi-Cal, FTB)", status="done", phase=2))
    cleared_alerts = {alert.id: alert for alert in evaluate_rules(estate, today=DEMO_TODAY)}
    assert "alert-state-agency-notice" not in cleared_alerts


def test_final_distribution_fires_at_low_urgency_for_a_fresh_estate() -> None:
    alerts = {alert.id: alert for alert in evaluate_rules(build_demo_estate(), today=DEMO_TODAY)}

    distribution = alerts["alert-final-distribution"]
    assert distribution.type == "deadline"
    assert distribution.severity == "info"
    assert isinstance(distribution.daysRemaining, int)
    assert distribution.daysRemaining > 30


def test_alert_output_is_stable_across_repeated_calls() -> None:
    estate = build_demo_estate()

    first = [alert.model_dump() for alert in evaluate_rules(estate, today=DEMO_TODAY)]
    second = [alert.model_dump() for alert in evaluate_rules(estate, today=DEMO_TODAY)]

    assert first == second
