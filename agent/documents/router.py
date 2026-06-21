from __future__ import annotations

import logging
import os

from llm.claude import DOCUMENT_MODEL, get_client
from observability.arize import set_span_attribute, span
from prompts.extraction import TYPE_DETECTION_PROMPT
from schemas.documents import DocumentExtraction, UnknownDocumentExtraction

from .bank_statement import parse_bank_statement
from .deed import parse_deed
from .will import parse_will


LOGGER = logging.getLogger(__name__)


async def parse_document_text(text: str, forced_type: str | None = None) -> DocumentExtraction:
    # When the user manually picks a type after auto-detection failed, honor their
    # choice instead of re-detecting. Types we have no structured parser for fall
    # through to the UnknownDocumentExtraction branch and are stored as-is.
    document_type = forced_type or _detect_type(text)
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
            extraction = UnknownDocumentExtraction(
                confidence=0.2,
                rawChunks=_emergency_chunks(text),
                reason=f"Document type '{document_type}' is not supported.",
            )
        set_span_attribute(current_span, "chunk_count", len(extraction.rawChunks))
        set_span_attribute(current_span, "confidence", extraction.confidence)
        return extraction


def detect_document_type(text: str) -> str:
    return _keyword_detect(text)


def _detect_type(text: str) -> str:
    sample = text[:1500].strip()
    if not sample:
        return "unknown"
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _keyword_detect(text)

    client = get_client()
    if client is None:
        return _keyword_detect(text)

    try:
        response = client.messages.create(
            model=DOCUMENT_MODEL,
            max_tokens=16,
            messages=[{
                "role": "user",
                "content": f"{TYPE_DETECTION_PROMPT}\n\nDOCUMENT BEGINNING:\n{sample}",
            }],
        )
        label = response.content[0].text.strip().lower()
        if label in ("will", "bank_statement", "deed"):
            return label
        return "unknown"
    except Exception:
        LOGGER.exception("Claude document type detection failed; using keyword fallback.")
        return _keyword_detect(text)


def _keyword_detect(text: str) -> str:
    lowered = text.lower()
    if "last will" in lowered or "testament" in lowered or "beneficiary" in lowered:
        return "will"
    if "statement" in lowered and ("balance" in lowered or "account" in lowered):
        return "bank_statement"
    if "grant deed" in lowered or "legal description" in lowered or "apn" in lowered:
        return "deed"
    return "unknown"


def _emergency_chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    return [cleaned[index : index + 500] for index in range(0, min(len(cleaned), 1500), 500)]
