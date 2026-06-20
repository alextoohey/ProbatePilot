from __future__ import annotations

from schemas.documents import DocumentExtraction, UnknownDocumentExtraction

from .bank_statement import parse_bank_statement
from .deed import parse_deed
from .will import parse_will


async def parse_document_text(text: str) -> DocumentExtraction:
    document_type = detect_document_type(text)
    if document_type == "will":
        return await parse_will(text)
    if document_type == "bank_statement":
        return await parse_bank_statement(text)
    if document_type == "deed":
        return await parse_deed(text)
    return UnknownDocumentExtraction(confidence=0.2, rawChunks=_chunks(text))


def detect_document_type(text: str) -> str:
    lowered = text.lower()
    if "last will" in lowered or "testament" in lowered or "beneficiary" in lowered:
        return "will"
    if "statement" in lowered or "account" in lowered or "balance" in lowered:
        return "bank_statement"
    if "grant deed" in lowered or "legal description" in lowered or "apn" in lowered:
        return "deed"
    return "unknown"


def _chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    return [cleaned[index : index + 500] for index in range(0, min(len(cleaned), 1500), 500)]

