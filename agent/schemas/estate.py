from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


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
TaskStatus = Literal["todo", "in_progress", "done", "blocked"]


class Executor(BaseModel):
    name: str
    email: str


class Asset(BaseModel):
    id: str
    type: AssetType
    description: str
    estimatedValue: float | None = None
    appraised: bool = False
    appraisedValue: float | None = None
    beneficiaryNamed: bool | None = None


class Debt(BaseModel):
    id: str
    creditor: str
    amount: float
    type: DebtType
    notified: bool = False
    notifiedDate: str | None = None
    claimFiled: bool | None = None


class Beneficiary(BaseModel):
    id: str
    name: str
    share: str | None = None
    specificBequest: str | None = None
    contactInfo: str | None = None


class UploadedDocument(BaseModel):
    id: str
    fileName: str
    documentType: str
    uploadedAt: str = Field(default_factory=utc_now_iso)
    source: str | None = None


class Task(BaseModel):
    id: str
    title: str
    status: TaskStatus = "todo"
    phase: int = Field(ge=1, le=6)
    dueDate: str | None = None
    relatedAlertId: str | None = None


class Alert(BaseModel):
    id: str
    severity: AlertSeverity
    type: AlertType
    title: str
    body: str
    rule: str
    daysRemaining: int | None = None
    actionRequired: str
    createdAt: str = Field(default_factory=utc_now_iso)
    dismissed: bool = False


class EstateState(BaseModel):
    id: str
    deceasedName: str
    dateOfDeath: str
    appointmentDate: str
    state: Literal["california"] = "california"
    executor: Executor
    assets: list[Asset] = Field(default_factory=list)
    debts: list[Debt] = Field(default_factory=list)
    beneficiaries: list[Beneficiary] = Field(default_factory=list)
    documents: list[UploadedDocument] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    phase: int = Field(default=1, ge=1, le=6)
    createdAt: str = Field(default_factory=utc_now_iso)
    updatedAt: str = Field(default_factory=utc_now_iso)

