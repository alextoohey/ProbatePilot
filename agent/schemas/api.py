from __future__ import annotations

from pydantic import BaseModel, Field

from .documents import BankStatementExtraction, DeedExtraction, UnknownDocumentExtraction, WillExtraction
from .estate import Alert, EstateState

AnyDocumentExtraction = WillExtraction | BankStatementExtraction | DeedExtraction | UnknownDocumentExtraction


class ParseDocumentResponse(BaseModel):
    estateId: str
    extraction: AnyDocumentExtraction
    alerts: list[Alert] = Field(default_factory=list)


class DeadlineAgentRequest(BaseModel):
    estateId: str = "demo-milligan"


class ChatRequest(BaseModel):
    estateId: str = "demo-milligan"
    message: str
    topK: int = 5


class GenerateLetterRequest(BaseModel):
    estateId: str = "demo-milligan"
    letterType: str = "creditor_notice"
    recipientName: str | None = None


class EstateResponse(BaseModel):
    estate: EstateState
