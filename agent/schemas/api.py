from __future__ import annotations

from pydantic import Field

from .documents import BankStatementExtraction, DeedExtraction, UnknownDocumentExtraction, WillExtraction
from .estate import Alert, ContractModel, EstateState

AnyDocumentExtraction = WillExtraction | BankStatementExtraction | DeedExtraction | UnknownDocumentExtraction


class SearchResult(ContractModel):
    text: str
    score: float
    source: str | None = None
    documentType: str | None = None
    chunkIndex: int | None = None
    estateId: str


class ParseDocumentResponse(ContractModel):
    estateId: str
    extraction: AnyDocumentExtraction
    # The resolved document type the file was stored under (the user's choice when
    # they manually selected one, otherwise the auto-detected type).
    documentType: str
    # True when auto-detection failed and no type was supplied, so the UI should
    # prompt the user to pick the document type. Nothing is stored in this case.
    needsTypeSelection: bool = False
    alerts: list[Alert] = Field(default_factory=list)


class DeadlineAgentRequest(ContractModel):
    estateId: str = "demo-milligan"


class ChatRequest(ContractModel):
    estateId: str = "demo-milligan"
    message: str
    topK: int = 5


class GenerateLetterRequest(ContractModel):
    estateId: str = "demo-milligan"
    letterType: str = "creditor_notice"
    recipientName: str | None = None


class EstateResponse(ContractModel):
    estate: EstateState
