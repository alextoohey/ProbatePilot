from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


AssetType = Literal[
    "real_estate",
    "bank_account",
    "retirement",
    "vehicle",
    "personal_property",
    "other",
]
DebtType = Literal["secured", "unsecured", "priority"]
AlertSeverity = Literal["critical", "warning", "info"]
AlertType = Literal["deadline", "liability", "missing_doc", "rule_violation"]
AlertTimingStatus = Literal["dated", "blocking", "prerequisite", "missing_data", "no_deadline"]
TaskStatus = Literal["todo", "in_progress", "done", "blocked"]
EstatePhase = Literal[1, 2, 3, 4, 5, 6]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Executor(ContractModel):
    name: str
    email: str


class Asset(ContractModel):
    id: str
    type: AssetType
    description: str
    estimatedValue: float | None = None
    appraised: bool = False
    appraisedValue: float | None = None
    beneficiaryNamed: bool | None = None


class Debt(ContractModel):
    id: str
    creditor: str
    amount: float
    type: DebtType
    notified: bool = False
    notifiedDate: str | None = None
    claimFiled: bool | None = None


class Beneficiary(ContractModel):
    id: str
    name: str
    share: str | None = None
    specificBequest: str | None = None
    contactInfo: str | None = None


class UploadedDocument(ContractModel):
    id: str
    fileName: str
    documentType: str
    uploadedAt: str = Field(default_factory=utc_now_iso)
    source: str | None = None


class Task(ContractModel):
    id: str
    title: str
    status: TaskStatus = "todo"
    phase: EstatePhase
    dueDate: str | None = None
    relatedAlertId: str | None = None


class Alert(ContractModel):
    id: str
    severity: AlertSeverity
    type: AlertType
    title: str
    body: str
    rule: str
    daysRemaining: int | None = None
    timingStatus: AlertTimingStatus = "no_deadline"
    actionRequired: str
    whatYouNeed: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    createdAt: str = Field(default_factory=utc_now_iso)
    dismissed: bool = False


class SavedLetter(ContractModel):
    id: str
    letterType: str
    recipientName: str | None = None
    draft: str
    savedAt: str = Field(default_factory=utc_now_iso)


class EstateState(ContractModel):
    id: str
    deceasedName: str
    dateOfDeath: str
    appointmentDate: str
    state: Literal["california"] = "california"
    county: str | None = None
    executor: Executor
    assets: list[Asset] = Field(default_factory=list)
    debts: list[Debt] = Field(default_factory=list)
    beneficiaries: list[Beneficiary] = Field(default_factory=list)
    documents: list[UploadedDocument] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    letters: list[SavedLetter] = Field(default_factory=list)
    phase: EstatePhase = 1
    createdAt: str = Field(default_factory=utc_now_iso)
    updatedAt: str = Field(default_factory=utc_now_iso)
