from __future__ import annotations

import os

from llm.claude import get_client, DOCUMENT_MODEL
from prompts.extraction import TYPE_DETECTION_PROMPT
from schemas.documents import DocumentExtraction, UnknownDocumentExtraction

from .bank_statement import parse_bank_statement
from .deed import parse_deed
from .will import parse_will


async def parse_document_text(text: str) -> DocumentExtraction:
    doc_type = _detect_type(text)
    if doc_type == "will":
        return await parse_will(text)
    if doc_type == "bank_statement":
        return await parse_bank_statement(text)
    if doc_type == "deed":
        return await parse_deed(text)
    return UnknownDocumentExtraction(
        confidence=0.0,
        rawChunks=_emergency_chunks(text),
        reason=f"Document type '{doc_type}' is not supported.",
    )


def detect_document_type(text: str) -> str:
    return _keyword_detect(text)


def _detect_type(text: str) -> str:
    """Ask Claude to classify the document type from the first ~1500 chars."""
    sample = text[:1500].strip()
    if not sample:
        return "unknown"
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _keyword_detect(text)
    try:
        client = get_client()
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
    except Exception as exc:
        print(f"[router] type detection failed, falling back to keyword: {exc}")
        return _keyword_detect(text)


def _keyword_detect(text: str) -> str:
    lowered = text.lower()
    if "last will" in lowered or "testament" in lowered:
        return "will"
    if "statement" in lowered and ("balance" in lowered or "account" in lowered):
        return "bank_statement"
    if "grant deed" in lowered or "legal description" in lowered or "apn" in lowered:
        return "deed"
    return "unknown"


def _emergency_chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    return [cleaned[i : i + 500] for i in range(0, min(len(cleaned), 1500), 500)]
