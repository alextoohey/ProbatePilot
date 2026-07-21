from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta

from schemas.estate import Alert, AlertTimingStatus, Asset, Debt, EstateState, Task, UploadedDocument


@dataclass(frozen=True)
class ProbateRule:
    id: str
    title: str
    statute: str
    trigger: str
    deadline: str
    consequence: str


CALIFORNIA_PROBATE_RULES = [
    ProbateRule("de-140", "DE-111 Probate Petition", "CA Probate Code §8000", "dateOfDeath", "ASAP", "No legal authority until filed"),
    ProbateRule("death-certificates", "Death certificates", "Operational requirement", "dateOfDeath", "Immediately", "Institutions require certified copies"),
    ProbateRule("letters-testamentary", "Letters Testamentary", "Court appointment prerequisite", "filedPetition", "After court appointment", "Estate administration requires proof of legal authority"),
    ProbateRule("de-160", "DE-160 Inventory & Appraisal", "CA Probate Code", "appointmentDate", "4 months", "Court sanctions and personal liability"),
    ProbateRule("creditor-notice", "Creditor notification", "CA Probate Code §9051", "appointmentDate", "30 days", "Personal liability for late distributions"),
    ProbateRule("estate-ein", "Estate EIN", "IRS SS-4", "estateBanking", "ASAP", "Cannot open estate bank account"),
    ProbateRule("estate-bank-account", "Estate bank account", "Operational prerequisite", "legalAuthorityAndEin", "ASAP", "Estate funds should be kept separate from personal funds"),
    ProbateRule("debt-resolution", "Debt resolution", "CA Probate Code §11420", "creditorNotice", "Before distribution", "Unresolved debts can block final distribution"),
    ProbateRule("final-1040", "Final 1040", "IRS", "dateOfDeath", "April 15 following year", "IRS penalties"),
    ProbateRule("debt-order", "Debt payment order", "CA Probate Code §11420", "beforeDistribution", "Sequential", "Out-of-order payments create personal liability"),
    ProbateRule("appraisal-needed", "Property appraisal needed", "CA Probate Code", "beforeDE160", "Before DE-160", "Blocks inventory filing"),
    ProbateRule(
        "state-agency-notice",
        "State agency notice (Medi-Cal, FTB, Victim Compensation, Child Support)",
        "CA Probate Code §9202",
        "appointmentDate",
        "90 days",
        "Personal liability for unpaid state claims, especially Medi-Cal estate recovery",
    ),
    ProbateRule(
        "final-distribution",
        "Petition for final distribution",
        "CA Probate Code §12200",
        "appointmentDate",
        "1 year (18 months if a federal estate tax return is due)",
        "Court can compel distribution via order to show cause",
    ),
]

# Rules that are real CA probate requirements but can't be evaluated
# deterministically with the fields EstateState currently tracks. Left out of
# CALIFORNIA_PROBATE_RULES (rather than kept as always-empty entries) so the
# rule count and the DeadlineAgent's `list_california_probate_rules` tool
# only ever report rules that can actually fire.
#
#   newspaper-notice (CA Probate Code §8121, form DE-121) — needs
#     firstPublicationDate and a record of each publication run. (Was
#     previously miscited as §9052, which is creditor-notice *contents*,
#     not newspaper publication.)
#   claim-period (CA Probate Code §9100) — needs firstPublicationDate plus a
#     distribution-status flag to gate "don't distribute before this closes".
#   form-1041 (IRS) — needs estateIncome and the estate's tax year end to
#     decide the >$600 filing trigger.


RULES_BY_ID = {rule.id: rule for rule in CALIFORNIA_PROBATE_RULES}
APPRAISABLE_ASSET_TYPES = {"real_estate", "vehicle", "personal_property", "other"}
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
TIMING_RANK = {"blocking": 0, "dated": 1, "prerequisite": 2, "missing_data": 3, "no_deadline": 4}
TYPE_RANK = {"liability": 0, "deadline": 1, "rule_violation": 2, "missing_doc": 3}


def evaluate_rules(estate: EstateState, today: date | None = None) -> list[Alert]:
    today = today or date.today()
    alerts: list[Alert] = []
    for rule_check in (
        _evaluate_de_140_probate_petition,
        _evaluate_death_certificates,
        _evaluate_letters_testamentary,
        _evaluate_estate_ein,
        _evaluate_estate_bank_account,
        _evaluate_de_160_inventory,
        _evaluate_creditor_notification,
        _evaluate_state_agency_notice,
        _evaluate_debt_resolution,
        _evaluate_final_1040,
        _evaluate_debt_payment_order,
        _evaluate_property_appraisal_needed,
        _evaluate_final_distribution,
    ):
        alerts.extend(rule_check(estate, today))

    return sorted(alerts, key=_alert_sort_key)


def _evaluate_de_140_probate_petition(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["de-140"]
    death_date = _required_date(estate, "dateOfDeath", rule, today)
    if isinstance(death_date, Alert):
        return [death_date]
    if _petition_filed(estate):
        return []

    days_since_death = (today - death_date).days
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-de-140-petition",
            severity="critical",
            alert_type="rule_violation",
            timing_status="blocking",
            title="Probate petition (DE-111) is not on file",
            body=(
                f"Rule de-140 ({rule.title}) is triggered by dateOfDeath={death_date.isoformat()}. "
                f"No DE-111/probate petition document is recorded after {days_since_death} days. "
                f"Consequence: {rule.consequence}."
            ),
            action="File the probate petition (DE-111) or upload the filed petition to establish legal authority.",
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
            timing_status="prerequisite",
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


def _evaluate_letters_testamentary(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["letters-testamentary"]
    if not _petition_filed(estate) or _has_legal_authority(estate):
        return []

    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-letters-testamentary",
            severity="critical",
            alert_type="missing_doc",
            timing_status="blocking",
            title="Court appointment and Letters Testamentary are pending",
            body=(
                "The probate petition is recorded, but no Letters Testamentary or equivalent proof of "
                "court appointment is recorded. Downstream estate administration remains blocked."
            ),
            action="Track the court appointment and upload the issued Letters Testamentary.",
            days_remaining=None,
        )
    ]


def _evaluate_de_160_inventory(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["de-160"]
    if not _has_legal_authority(estate) or not _assets(estate) or _rule_completed(estate, "alert-de-160-inventory", "alert-de-160-ready"):
        return []
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
                timing_status="dated",
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
            timing_status="dated",
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
    if not _has_legal_authority(estate) or _creditor_notice_recorded(estate):
        return []
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
            timing_status="dated",
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


def _evaluate_state_agency_notice(estate: EstateState, today: date) -> list[Alert]:
    """CA Probate Code §9202: within 90 days of Letters, the personal
    representative must notify the Department of Health Care Services
    (Medi-Cal estate recovery), the Franchise Tax Board, the Victim
    Compensation Board, and any child support agency with a potential claim.
    Medi-Cal estate recovery in particular is a real, common personal-
    liability trap that isn't otherwise tracked anywhere in this app."""
    rule = RULES_BY_ID["state-agency-notice"]
    if not _has_legal_authority(estate) or _state_agency_notice_recorded(estate):
        return []
    appointment = _required_date(estate, "appointmentDate", rule, today)
    if isinstance(appointment, Alert):
        return [appointment]

    due = appointment + relativedelta(days=90)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-state-agency-notice",
            severity="critical",
            alert_type="liability",
            timing_status="dated",
            title="State agencies have not been notified",
            body=(
                f"Rule state-agency-notice ({rule.title}; {rule.statute}) is due {due.isoformat()} "
                f"from appointmentDate={appointment.isoformat()}. California requires notifying the "
                "Department of Health Care Services (Medi-Cal estate recovery), the Franchise Tax "
                "Board, the Victim Compensation Board, and any child support agency with a potential "
                f"claim against the decedent. Consequence: {rule.consequence}."
            ),
            action=(
                "Send the required notices to DHCS, the Franchise Tax Board, the Victim Compensation "
                "Board, and any child support agency, and record the date sent."
            ),
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_estate_ein(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["estate-ein"]
    if not _has_legal_authority(estate) or _estate_ein_recorded(estate):
        return []

    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-estate-ein",
            severity="warning",
            alert_type="missing_doc",
            timing_status="prerequisite",
            title="Estate EIN is not recorded",
            body=(
                "Legal authority is recorded, but no estate EIN, SS-4 confirmation, or completed EIN task is recorded. "
                f"Consequence: {rule.consequence}."
            ),
            action="Apply for or record the estate EIN before opening or using estate banking.",
            days_remaining=None,
        )
    ]


def _evaluate_estate_bank_account(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["estate-bank-account"]
    if not _has_legal_authority(estate) or not _estate_ein_recorded(estate) or _estate_bank_account_recorded(estate):
        return []

    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-estate-bank-account",
            severity="warning",
            alert_type="rule_violation",
            timing_status="prerequisite",
            title="Estate bank account is not recorded",
            body=(
                "Legal authority and the estate EIN are recorded, but no dedicated estate bank account "
                "or completed account-opening task is recorded."
            ),
            action="Open a dedicated estate bank account and record the account in the estate file.",
            days_remaining=None,
        )
    ]


def _evaluate_debt_resolution(estate: EstateState, today: date) -> list[Alert]:
    rule = RULES_BY_ID["debt-resolution"]
    debts = _debts(estate)
    if (
        not _has_legal_authority(estate)
        or not debts
        or not _creditor_notice_recorded(estate)
        or _rule_completed(estate, "alert-debt-resolution")
    ):
        return []

    creditor_list = _join_descriptions(debt.creditor for debt in debts)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-debt-resolution",
            severity="warning",
            alert_type="liability",
            timing_status="prerequisite",
            title="Known estate debts still need resolution",
            body=f"Creditor notice is recorded for the known debts from {creditor_list}, but debt resolution is not recorded.",
            action="Review and resolve valid estate debts in the required payment order before distribution.",
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
            timing_status="dated",
            title="Final personal 1040 is not recorded",
            body=(
                f"Rule final-1040 ({rule.title}) is due {due.isoformat()} from dateOfDeath={death_date.isoformat()}. "
                f"Consequence: {rule.consequence}."
            ),
            action="Confirm whether a final personal 1040 is required and record the filing plan.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_debt_payment_order(estate: EstateState, today: date) -> list[Alert]:
    """CA probate pays secured creditors before unsecured/priority ones,
    which come before beneficiary distributions. EstateState has no
    payment-status field to catch an out-of-order *payment* directly, but
    Debt.notified is a real, tracked signal — notifying unsecured or
    priority creditors while a secured creditor still hasn't been notified
    is the earliest observable sign the order is being violated."""
    rule = RULES_BY_ID["debt-order"]
    debts = _debts(estate)
    unnotified_secured = [d for d in debts if d.type == "secured" and not d.notified]
    notified_unsecured_or_priority = [d for d in debts if d.type in ("unsecured", "priority") and d.notified]
    if not unnotified_secured or not notified_unsecured_or_priority or _rule_completed(estate, "alert-debt-order"):
        return []

    creditor_list = _join_descriptions(debt.creditor for debt in unnotified_secured)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-debt-order",
            severity="critical",
            alert_type="rule_violation",
            timing_status="blocking",
            title="Creditors are being notified out of payment order",
            body=(
                f"Rule debt-order ({rule.title}) requires secured creditors to be notified and paid before "
                f"unsecured or priority creditors. Secured creditors not yet notified: {creditor_list}, while "
                f"at least one unsecured or priority creditor already has been. Consequence: {rule.consequence}."
            ),
            action="Pause unsecured or priority creditor payments and notify the remaining secured creditors first.",
            days_remaining=None,
        )
    ]


def _evaluate_final_distribution(estate: EstateState, today: date) -> list[Alert]:
    """CA Probate Code §12200: the personal representative must petition for
    final distribution, or file a status report, within one year of Letters
    issuing (18 months if a federal estate tax return is required). §12201
    lets the court compel this via an order to show cause."""
    rule = RULES_BY_ID["final-distribution"]
    if not _has_legal_authority(estate) or _final_distribution_recorded(estate):
        return []
    appointment = _required_date(estate, "appointmentDate", rule, today)
    if isinstance(appointment, Alert):
        return [appointment]

    due = appointment + relativedelta(years=1)
    return [
        _alert(
            rule=rule,
            today=today,
            alert_id="alert-final-distribution",
            severity=_deadline_severity(due, today),
            alert_type="deadline",
            timing_status="dated",
            title="Petition for final distribution is not on file",
            body=(
                f"Rule final-distribution ({rule.title}; {rule.statute}) is due {due.isoformat()} "
                f"from appointmentDate={appointment.isoformat()}. California requires the personal "
                "representative to petition for final distribution, or file a status report with the "
                "court, within one year of Letters issuing (18 months if a federal estate tax return "
                f"is required). Consequence: {rule.consequence}."
            ),
            action="File the petition for final distribution, or a status report if the estate isn't ready to close.",
            days_remaining=(due - today).days,
        )
    ]


def _evaluate_property_appraisal_needed(estate: EstateState, today: date) -> list[Alert]:
    # Intentionally a no-op: unappraised-asset detection already lives in
    # _evaluate_de_160_inventory (the only place appraisal status blocks a
    # deadline). This rule stays listed for the DeadlineAgent's rule catalog
    # so the model knows appraisal requirements exist, without duplicating
    # the DE-160 alert.
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
        timing_status="missing_data",
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
    timing_status: AlertTimingStatus,
    title: str,
    body: str,
    action: str,
    days_remaining: int | None,
) -> Alert:
    if timing_status == "dated" and days_remaining is None:
        timing_status = "no_deadline"
    elif timing_status != "dated" and days_remaining is not None:
        timing_status = "dated"

    return Alert(
        id=alert_id,
        severity=severity,
        type=alert_type,
        title=title,
        body=body,
        rule=f"{rule.id}: {rule.title} ({rule.statute})",
        daysRemaining=days_remaining,
        timingStatus=timing_status,
        actionRequired=action,
        createdAt=f"{today.isoformat()}T00:00:00+00:00",
    )


def _petition_filed(estate: EstateState) -> bool:
    return (
        _has_document(estate, "de-111", "de-140", "probate petition")
        or _task_done(estate, "file probate petition", "de-111", "de-140")
        or _rule_completed(estate, "alert-de-140-petition")
    )


def _has_legal_authority(estate: EstateState) -> bool:
    return (
        _has_document(estate, "letters testamentary", "letters of administration")
        or _task_done(estate, "letters testamentary", "court appointment")
        or _rule_completed(estate, "alert-letters-testamentary")
    )


def _estate_ein_recorded(estate: EstateState) -> bool:
    return (
        _has_document(estate, "estate ein", "ein confirmation", "ss-4")
        or _task_done(estate, "estate ein", "obtain ein")
        or _rule_completed(estate, "alert-estate-ein")
    )


def _estate_bank_account_recorded(estate: EstateState) -> bool:
    has_estate_account_asset = any(
        asset.type == "bank_account" and "estate" in _normalize(asset.description)
        for asset in _assets(estate)
    )
    return (
        has_estate_account_asset
        or _has_document(estate, "estate bank account", "estate account")
        or _task_done(estate, "estate bank account", "dedicated estate account")
        or _rule_completed(estate, "alert-estate-bank-account")
    )


def _creditor_notice_recorded(estate: EstateState) -> bool:
    debts = _debts(estate)
    return (
        bool(debts) and all(debt.notified for debt in debts)
        or _has_document(estate, "creditor notice")
        or _task_done(estate, "notify all known creditors", "creditor notice")
        or _rule_completed(estate, "alert-creditor-notice")
    )


def _state_agency_notice_recorded(estate: EstateState) -> bool:
    return (
        _has_document(estate, "state agency notice", "medi-cal notice", "dhcs notice", "9202")
        or _task_done(estate, "notify state agencies", "medi-cal", "dhcs")
        or _rule_completed(estate, "alert-state-agency-notice")
    )


def _final_distribution_recorded(estate: EstateState) -> bool:
    return (
        _has_document(estate, "final distribution", "petition for final distribution", "status report")
        or _task_done(estate, "final distribution", "status report")
        or _rule_completed(estate, "alert-final-distribution")
    )


def _rule_completed(estate: EstateState, *alert_ids: str) -> bool:
    ids = set(alert_ids)
    if any(alert.id in ids and alert.dismissed for alert in estate.alerts):
        return True
    generated_task_ids = {f"task-{alert_id.removeprefix('alert-')}" for alert_id in ids}
    return any(
        task.status == "done" and (task.relatedAlertId in ids or task.id in generated_task_ids)
        for task in estate.tasks
    )


def _alert_sort_key(alert: Alert) -> tuple[int, int, int, int, str]:
    days_remaining = 999999 if alert.daysRemaining is None else alert.daysRemaining
    return (
        SEVERITY_RANK[alert.severity],
        TIMING_RANK.get(alert.timingStatus, 4),
        TYPE_RANK.get(alert.type, 3),
        days_remaining,
        alert.id,
    )


def derive_alert_timing_status(alert: Alert) -> AlertTimingStatus:
    if alert.daysRemaining is not None:
        return "dated"
    alert_id = alert.id.casefold()
    title = alert.title.casefold()
    if "-missing-" in alert_id or "missing data" in title:
        return "missing_data"
    if alert_id.startswith("alert-de-140") or "blocking" in title or "legal authority" in alert.body.casefold():
        return "blocking"
    if alert_id.startswith("alert-estate-ein") or alert_id.startswith("alert-death-certificates"):
        return "prerequisite"
    return "no_deadline"


def alert_sort_key(alert: Alert) -> tuple[int, int, int, int, str]:
    return _alert_sort_key(alert)


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
