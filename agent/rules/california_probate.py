from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta

from schemas.estate import Alert, EstateState


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


def evaluate_rules(estate: EstateState, today: date | None = None) -> list[Alert]:
    today = today or date.today()
    alerts: list[Alert] = []
    appointment = date.fromisoformat(estate.appointmentDate)

    unappraised_assets = [asset for asset in estate.assets if asset.type in {"real_estate", "vehicle"} and not asset.appraised]
    if unappraised_assets:
        due = appointment + relativedelta(months=4)
        days_remaining = (due - today).days
        alerts.append(
            Alert(
                id="alert-de-160-inventory",
                severity="critical",
                type="deadline",
                title="DE-160 Inventory & Appraisal is blocked",
                body="The estate has assets that still need appraisal before the inventory can be filed.",
                rule="DE-160 Inventory & Appraisal",
                daysRemaining=days_remaining,
                actionRequired="Schedule appraisals and prepare the DE-160 packet.",
            )
        )

    unnotified_debts = [debt for debt in estate.debts if not debt.notified]
    if unnotified_debts:
        due = appointment + relativedelta(days=30)
        days_remaining = (due - today).days
        alerts.append(
            Alert(
                id="alert-creditor-notice",
                severity="critical",
                type="liability",
                title="Known creditors have not been notified",
                body="Known creditors must receive certified notice before distributions are made.",
                rule="CA Probate Code §9051",
                daysRemaining=days_remaining,
                actionRequired="Send certified creditor notices to each known creditor.",
            )
        )

    return sorted(alerts, key=lambda alert: {"critical": 0, "warning": 1, "info": 2}[alert.severity])

