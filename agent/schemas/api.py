from __future__ import annotations

from pydantic import Field

from .documents import BankStatementExtraction, CreditorNoticeExtraction, DeedExtraction, UnknownDocumentExtraction, WillExtraction
from .estate import Alert, ContractModel, EstateState, SavedLetter

AnyDocumentExtraction = WillExtraction | BankStatementExtraction | DeedExtraction | CreditorNoticeExtraction | UnknownDocumentExtraction


class SearchResult(ContractModel):
    text: str
    score: float
    source: str | None = None
    documentType: str | None = None
    chunkIndex: int | None = None
    estateId: str


class ParseDocumentResponse(ContractModel):
    estateId: str
    fileName: str | None = None
    extraction: AnyDocumentExtraction
    # The resolved document type the file was stored under (the user's choice when
    # they manually selected one, otherwise the auto-detected type).
    documentType: str
    # True when auto-detection failed and no type was supplied, so the UI should
    # prompt the user to pick the document type. Nothing is stored in this case.
    needsTypeSelection: bool = False
    reviewMessage: str | None = None
    alerts: list[Alert] = Field(default_factory=list)


class ParseDocumentFailure(ContractModel):
    fileName: str
    detail: str
    statusCode: int = 422


class ParseDocumentsResponse(ContractModel):
    estateId: str
    results: list[ParseDocumentResponse] = Field(default_factory=list)
    failed: list[ParseDocumentFailure] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)


class DeadlineAgentRequest(ContractModel):
    estateId: str = "demo-milligan"


class CompleteAlertRequest(ContractModel):
    estateId: str = "demo-milligan"
    alertId: str


class ChatRequest(ContractModel):
    estateId: str = "demo-milligan"
    message: str
    topK: int = 5
    sessionId: str | None = None


class ChatMessage(ContractModel):
    role: str  # "user" | "assistant"
    content: str
    createdAt: str


class ChatHistoryResponse(ContractModel):
    estateId: str
    sessionId: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatSession(ContractModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messageCount: int = 0
    preview: str | None = None


class ChatSessionsResponse(ContractModel):
    estateId: str
    sessions: list[ChatSession] = Field(default_factory=list)


class ChatSessionResponse(ContractModel):
    estateId: str
    session: ChatSession
    messages: list[ChatMessage] = Field(default_factory=list)


class NotifyEmailRequest(ContractModel):
    estateId: str = "demo-milligan"
    recipientEmail: str | None = None
    # "alerts" = current open alerts; "weekly" = the Monday recap.
    kind: str = "alerts"


class NotifyEmailResponse(ContractModel):
    estateId: str
    sent: bool
    reason: str
    recipient: str | None = None
    alertCount: int = 0
    # The composed email, returned so the UI can preview the exact message
    # (and demonstrate a sample even when sending isn't configured).
    subject: str = ""
    body: str = ""


class ChatSuggestionsRequest(ContractModel):
    estateId: str = "demo-milligan"


class ChatSuggestionsResponse(ContractModel):
    estateId: str
    suggestions: list[str] = Field(default_factory=list)


class GenerateLetterRequest(ContractModel):
    estateId: str = "demo-milligan"
    letterType: str = "creditor_notice"
    recipientName: str | None = None
    # Free-text description for a custom letter (letterType == "custom").
    instructions: str | None = None


class SaveLetterRequest(ContractModel):
    estateId: str
    letterType: str
    recipientName: str | None = None
    draft: str


class SaveLetterResponse(ContractModel):
    estateId: str
    letter: SavedLetter


class EstateResponse(ContractModel):
    estate: EstateState
