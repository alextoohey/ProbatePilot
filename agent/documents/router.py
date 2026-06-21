from __future__ import annotations

from observability.arize import set_span_attribute, span
from schemas.documents import DocumentExtraction, UnknownDocumentExtraction

from .bank_statement import parse_bank_statement
from .deed import parse_deed
from .will import parse_will


async def parse_document_text(text: str) -> DocumentExtraction:
    document_type = detect_document_type(text)
    with span(
        "documents.parse",
        action_type="document_parse",
        doc_type=document_type,
        input_length=len(text),
    ) as current_span:
        if document_type == "will":
            extraction = await parse_will(text)
        elif document_type == "bank_statement":
            extraction = await parse_bank_statement(text)
        elif document_type == "deed":
            extraction = await parse_deed(text)
        else:
            extraction = UnknownDocumentExtraction(confidence=0.2, rawChunks=_chunks(text))
        set_span_attribute(current_span, "chunk_count", len(extraction.rawChunks))
        set_span_attribute(current_span, "confidence", extraction.confidence)
        return extraction


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
