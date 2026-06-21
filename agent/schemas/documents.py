from __future__ import annotations

from typing import Literal

from pydantic import Field

from .estate import Asset, Beneficiary, Debt
from .estate import ContractModel


DocumentType = Literal["will", "bank_statement", "deed", "creditor_notice", "unknown"]


class DocumentExtraction(ContractModel):
    documentType: DocumentType
    confidence: float = Field(default=0.0, ge=0, le=1)
    rawChunks: list[str] = Field(default_factory=list)


class WillExtraction(DocumentExtraction):
    documentType: Literal["will"] = "will"
    executorName: str | None = None
    beneficiaries: list[Beneficiary] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    trustClauses: list[str] = Field(default_factory=list)
    specialInstructions: list[str] = Field(default_factory=list)
    codicils: list[str] = Field(default_factory=list)


class BankStatementExtraction(DocumentExtraction):
    documentType: Literal["bank_statement"] = "bank_statement"
    institution: str | None = None
    accountLast4: str | None = None
    accountType: str | None = None
    balance: float | None = None
    statementDate: str | None = None
    notableTransactions: list[str] = Field(default_factory=list)


class DeedExtraction(DocumentExtraction):
    documentType: Literal["deed"] = "deed"
    propertyAddress: str | None = None
    apn: str | None = None
    legalDescription: str | None = None
    grantor: str | None = None
    grantee: str | None = None
    recordedDate: str | None = None
    estimatedValue: float | None = None


class CreditorNoticeExtraction(DocumentExtraction):
    documentType: Literal["creditor_notice"] = "creditor_notice"
    creditorName: str | None = None
    amountOwed: float | None = None
    accountNumber: str | None = None
    debtType: Literal["secured", "unsecured", "priority"] = "unsecured"
    debts: list[Debt] = Field(default_factory=list)


class UnknownDocumentExtraction(DocumentExtraction):
    documentType: Literal["unknown"] = "unknown"
    reason: str = "Document type could not be determined."
