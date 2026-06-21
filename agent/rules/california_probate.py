from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from dateutil.relativedelta import relativedelta

from schemas.estate import Alert, Asset, Debt, EstateState, Task, UploadedDocument


@dataclass(frozen=True)
class ProbateRule:
    id: str
    title: str
    statute: str
    trigger: str
    deadline: str
    consequence: str


CALIFORNIA_PROBATE_RULES = [
    ProbateRule("de-140", "DE-140 Probate Petition", "CA Probate Code", "dateOfDeath", "ASAP", "No legal authority until filed"),
    ProbateRule("death-certificates", "Death certificates", "Operational requirement", "dateOfDeath", "Immediately", "Institutions require certified copies"),
    ProbateRule("de-160", "DE-160 Inventory & Appraisal", "CA Probate Code", "appointmentDate", "4 months", "Court sanctions and personal liability"),
    ProbateRule("creditor-notice", "Creditor notification", "CA Probate Code §9051", "appointmentDate", "30 days", "Personal liability for late distributions"),
    ProbateRule("newspaper-notice", "Newspaper notice to creditors", "CA Probate Code §9052", "firstPublicationDate", "3 weeks", "Notice violation"),
    ProbateRule("claim-period", "Creditor claim period closes", "CA Probate Code", "firstPublicationDate", "4 months", "Cannot distribute before close"),
    ProbateRule("estate-ein", "Estate EIN", "IRS SS-4", "estateBanking", "ASAP", "Cannot open estate bank account"),
    ProbateRule("final-1040", "Final 1040", "IRS", "dateOfDeath", "April 15 following year", "IRS penalties"),
    ProbateRule("form-1041", "Form 1041", "IRS", "estateIncome", "April 15 following year", "IRS penalties"),
    ProbateRule("debt-order", "Debt payment order", "CA Probate Code", "beforeDistribution", "Sequential", "Out-of-order payments create personal liability"),
    ProbateRule("appraisal-needed", "Property appraisal needed", "CA Probate Code", "beforeDE160", "Before DE-160", "Blocks inventory filing"),
]


RULES_BY_ID = {rule.id: rule for rule in CALIFORNIA_PROBATE_RULES}
APPRAISABLE_ASSET_TYPES = {"real_estate", "vehicle", "personal_property", "other"}
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def evaluate_rules(estate: EstateState, today: date | None = None) -> list[Alert]:
    today = today or date.today()
    alerts: list[Alert] = []
    for rule_check in (
        _evaluate_de_140_probate_petition,
        _evaluate_death_certificates,
        _evaluate_de_160_inventory,
        _evaluate_creditor_notification,
        _evaluate_newspaper_notice,
        _evaluate_claim_period,
        _evaluate_estate_ein,
        _evaluate_final_1040,
        _evaluate_form_1041,
        _evaluate_debt_payment_order,
        _evaluate_property_appraisal_needed,
    ):
        alerts.extend(rule_check(estate, today))

    return sorted(alerts, key=_alert_sort_key)


def _evaluate_de_140_probate_petition(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["de-140"]
    death_date = _required_date(estate, "dateOfDeath", rule, today)
    if isinstance(death_date, Alert):
        return [death_date]
    if _has_document(estate, "de-140", "probate petition") or _task_done(estate, "probate petition", "de-140"):
        return []

    days_since_death = (today - death_date).days
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-de-140-petition",
            severity="warning",
            alert_type="missing_doc",
            title="Probate petition status is missing",
            body=(
                f"Rule de-140 ({rule.title}) is triggered by dateOfDeath={death_date.isoformat()}. "
                f"No DE-140/probate petition document or completed task is recorded after {days_since_death} days. "
                f"Consequence: {rule.consequence}."
            ),
            action="Confirm the petition filing status and upload the DE-140 or mark the filing task done.",
            days_remaining=None,
        )
    ]


def _evaluate_death_certificates(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["death-certificates"]
    death_date = _required_date(estate, "dateOfDeath", rule, today)
    if isinstance(death_date, Alert):
        return [death_date]
    if _has_document(estate, "death certificate") or _task_done(estate, "death certificate"):
        return []

    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-death-certificates",
            severity="warning",
            alert_type="missing_doc",
            title="Certified death certificates are not recorded",
            body=(
                f"Rule death-certificates ({rule.title}) is triggered by dateOfDeath={death_date.isoformat()}. "
                "No death certificate document or completed ordering task is recorded. "
                f"Consequence: {rule.consequence}."
            ),
            action="Order certified death certificates or mark the existing ordering task done.",
            days_remaining=None,
        )
    ]


def _evaluate_de_160_inventory(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["de-160"]
    appointment = _required_date(estate, "appointmentDate", rule, today)
    if isinstance(appointment, Alert):
        return [appointment]
    if _has_document(estate, "de-160", "inventory and appraisal") or _task_done(estate, "de-160", "inventory and appraisal"):
        return []

    due = appointment + relativedelta(months=4)
    unappraised_assets = _unappraised_assets(estate)
    if unappraised_assets:
        asset_list = _join_descriptions(asset.description for asset in unappraised_assets)
        return [
            _alert(
                rule=rule,
                today=today,
                alert_id="alert-de-160-inventory",
                severity="critical",
                alert_type="deadline",
                title="DE-160 Inventory & Appraisal is blocked",
                body=(
                    f"Rule de-160 ({rule.title}) is due {due.isoformat()} from appointmentDate={appointment.isoformat()}. "
                    f"Appraisals are missing for: {asset_list}. "
                    f"Consequence: {rule.consequence}."
                ),
                action="Schedule appraisals and prepare the DE-160 packet before filing.",
                days_remaining=(due - today).days,
            )
        ]

    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-de-160-ready",
            severity=_deadline_severity(due, today),
            alert_type="deadline",
            title="DE-160 Inventory & Appraisal filing is pending",
            body=(
                f"Rule de-160 ({rule.title}) is due {due.isoformat()} from appointmentDate={appointment.isoformat()}. "
                "All currently appraisable assets are marked appraised, but no filing document or completed task is recorded. "
                f"Consequence: {rule.consequence}."
            ),
            action="File DE-160 or upload the filed inventory and appraisal.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_creditor_notification(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["creditor-notice"]
    appointment = _required_date(estate, "appointmentDate", rule, today)
    if isinstance(appointment, Alert):
        return [appointment]

    unnotified_debts = [debt for debt in _debts(estate) if not debt.notified]
    if not unnotified_debts:
        return []

    due = appointment + relativedelta(days=30)
    creditor_list = _join_descriptions(debt.creditor for debt in unnotified_debts)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-creditor-notice",
            severity="critical",
            alert_type="liability",
            title="Known creditors have not been notified",
            body=(
                f"Rule creditor-notice ({rule.title}; {rule.statute}) is due {due.isoformat()} "
                f"from appointmentDate={appointment.isoformat()}. Unnotified creditors: {creditor_list}. "
                f"Consequence: {rule.consequence}."
            ),
            action="Send certified creditor notices to each known creditor and record the notified date.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_newspaper_notice(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["newspaper-notice"]
    # TODO: Add firstPublicationDate/publicationRuns to EstateState so this can verify the 3-week notice directly.
    if not hasattr(estate, "firstPublicationDate"):
        return []
    publication_date = _required_date(estate, "firstPublicationDate", rule, today)
    if isinstance(publication_date, Alert):
        return [publication_date]

    due = publication_date + relativedelta(weeks=3)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-newspaper-notice",
            severity=_deadline_severity(due, today),
            alert_type="deadline",
            title="Newspaper creditor notice completion is not recorded",
            body=(
                f"Rule newspaper-notice ({rule.title}; {rule.statute}) runs from "
                f"firstPublicationDate={publication_date.isoformat()} through {due.isoformat()}. "
                f"Consequence: {rule.consequence}."
            ),
            action="Record all required publication runs or upload proof of publication.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_claim_period(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["claim-period"]
    # TODO: Add firstPublicationDate and distribution status to EstateState to gate distributions deterministically.
    if not hasattr(estate, "firstPublicationDate"):
        return []
    publication_date = _required_date(estate, "firstPublicationDate", rule, today)
    if isinstance(publication_date, Alert):
        return [publication_date]

    close_date = publication_date + relativedelta(months=4)
    if today < close_date:
        return [
            _alert(
                rule=rule,
                today=today,
                alert_id="alert-claim-period-open",
                severity="info",
                alert_type="deadline",
                title="Creditor claim period is still open",
                body=(
                    f"Rule claim-period ({rule.title}) closes {close_date.isoformat()} from "
                    f"firstPublicationDate={publication_date.isoformat()}. Consequence: {rule.consequence}."
                ),
                action="Do not make beneficiary distributions until the creditor claim period closes.",
                days_remaining=(close_date - today).days,
            )
        ]
    return []


def _evaluate_estate_ein(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["estate-ein"]
    # TODO: Add hasEstateEin and estateBankAccountOpened to EstateState. Documents/tasks are a temporary proxy.
    has_banking_asset = any(asset.type == "bank_account" for asset in _assets(estate))
    if not has_banking_asset or _has_document(estate, "ein", "ss-4") or _task_done(estate, "ein", "ss-4"):
        return []

    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-estate-ein",
            severity="warning",
            alert_type="missing_doc",
            title="Estate EIN is not recorded",
            body=(
                "Rule estate-ein (Estate EIN) is triggered by estate banking activity. "
                "The estate has a bank account asset, but no EIN/SS-4 document or completed task is recorded. "
                f"Consequence: {rule.consequence}."
            ),
            action="Apply for or record the estate EIN before opening or using estate banking.",
            days_remaining=None,
        )
    ]


def _evaluate_final_1040(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["final-1040"]
    death_date = _required_date(estate, "dateOfDeath", rule, today)
    if isinstance(death_date, Alert):
        return [death_date]
    if _has_document(estate, "1040", "final tax") or _task_done(estate, "1040", "final tax"):
        return []

    due = date(death_date.year + 1, 4, 15)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-final-1040",
            severity=_deadline_severity(due, today),
            alert_type="deadline",
            title="Final personal 1040 is not recorded",
            body=(
                f"Rule final-1040 ({rule.title}) is due {due.isoformat()} from dateOfDeath={death_date.isoformat()}. "
                f"Consequence: {rule.consequence}."
            ),
            action="Confirm whether a final personal 1040 is required and record the filing plan.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_form_1041(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["form-1041"]
    # TODO: Add estateIncome and taxYearClose to EstateState. The current schema cannot decide the >$600 trigger.
    estate_income = getattr(estate, "estateIncome", None)
    if estate_income is None:
        return []
    if estate_income <= 600 or _has_document(estate, "1041") or _task_done(estate, "1041"):
        return []

    death_date = _required_date(estate, "dateOfDeath", rule, today)
    if isinstance(death_date, Alert):
        return [death_date]
    due = date(death_date.year + 1, 4, 15)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-form-1041",
            severity=_deadline_severity(due, today),
            alert_type="deadline",
            title="Estate Form 1041 is not recorded",
            body=(
                f"Rule form-1041 ({rule.title}) is due {due.isoformat()} because estateIncome={estate_income}. "
                f"Consequence: {rule.consequence}."
            ),
            action="Prepare Form 1041 or record why it is not required.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_debt_payment_order(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["debt-order"]
    # TODO: Add debt payment status and beneficiary distribution records to EstateState.
    return []


def _evaluate_property_appraisal_needed(estate: EstateState, today: date) -> list[Alert]:
    # Covered by the DE-160 rule until appraisal documents have their own schema state.
    return []


def _required_date(estate: EstateState, field_name: str, rule: ProbateRule, today: date) -> date | Alert:
    value = getattr(estate, field_name, None)
    if not value:
        return _missing_data_alert(
            rule=rule,
            field_name=field_name,
            today=today,
            action=f"Add {field_name} to the estate state before evaluating {rule.title}.",
        )
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return _missing_data_alert(
            rule=rule,
            field_name=field_name,
            today=today,
            action=f"Correct {field_name} to ISO date format YYYY-MM-DD before evaluating {rule.title}.",
            raw_value=str(value),
        )


def _missing_data_alert(
    *,
    rule: ProbateRule,
    field_name: str,
    today: date,
    action: str,
    raw_value: str | None = None,
) -> Alert:
    raw_detail = f" Current value: {raw_value!r}." if raw_value is not None else ""
    return _alert(
        rule=rule,
        today=today,
        alert_id=f"alert-{rule.id}-missing-{_slug(field_name)}",
        severity="warning",
        alert_type="missing_doc",
        title=f"Missing data blocks {rule.title}",
        body=(
            f"Rule {rule.id} ({rule.title}) requires {field_name} to evaluate deterministically."
            f"{raw_detail} Consequence if ignored: {rule.consequence}."
        ),
        action=action,
        days_remaining=None,
    )


def _alert(
    *,
    rule: ProbateRule,
    today: date,
    alert_id: str,
    severity: str,
    alert_type: str,
    title: str,
    body: str,
    action: str,
    days_remaining: int | None,
) -> Alert:
    return Alert(
        id=alert_id,
        severity=severity,
        type=alert_type,
        title=title,
        body=body,
        rule=f"{rule.id}: {rule.title} ({rule.statute})",
        daysRemaining=days_remaining,
        actionRequired=action,
        createdAt=f"{today.isoformat()}T00:00:00+00:00",
    )


def _alert_sort_key(alert: Alert) -> tuple[int, int, str]:
    missing_due = 999999 if alert.daysRemaining is None else alert.daysRemaining
    return (SEVERITY_RANK[alert.severity], missing_due, alert.id)


def _deadline_severity(due: date, today: date) -> str:
    days_remaining = (due - today).days
    if days_remaining < 0:
        return "critical"
    if days_remaining <= 30:
        return "warning"
    return "info"


def _unappraised_assets(estate: EstateState) -> list[Asset]:
    return [asset for asset in _assets(estate) if asset.type in APPRAISABLE_ASSET_TYPES and not asset.appraised]


def _assets(estate: EstateState) -> list[Asset]:
    return list(_safe_iter(estate.assets))


def _debts(estate: EstateState) -> list[Debt]:
    return list(_safe_iter(estate.debts))


def _beneficiaries(estate: EstateState) -> list[object]:
    return list(_safe_iter(estate.beneficiaries))


def _tasks(estate: EstateState) -> list[Task]:
    return list(_safe_iter(estate.tasks))


def _documents(estate: EstateState) -> list[UploadedDocument]:
    return list(_safe_iter(estate.documents))


def _safe_iter(items: Iterable[object] | None) -> Iterable[object]:
    return items or []


def _has_document(estate: EstateState, *needles: str) -> bool:
    normalized_needles = [_normalize(needle) for needle in needles]
    for document in _documents(estate):
        haystack = _normalize(f"{document.documentType} {document.fileName}")
        if any(needle in haystack for needle in normalized_needles):
            return True
    return False


def _task_done(estate: EstateState, *needles: str) -> bool:
    normalized_needles = [_normalize(needle) for needle in needles]
    for task in _tasks(estate):
        if task.status != "done":
            continue
        title = _normalize(task.title)
        if any(needle in title for needle in normalized_needles):
            return True
    return False


def _join_descriptions(values: Iterable[str]) -> str:
    descriptions = [value for value in values if value]
    return ", ".join(descriptions) if descriptions else "unknown assets"


def _normalize(value: str) -> str:
    return value.casefold().replace("_", " ").replace("-", " ")


def _slug(value: str) -> str:
    return _normalize(value).replace("/", " ").replace(" ", "-")
