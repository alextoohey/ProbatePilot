from __future__ import annotations

import difflib
import logging
import os
import re

from llm.claude import DOCUMENT_MODEL, get_client
from observability.arize import set_span_attribute, span
from prompts.extraction import TYPE_DETECTION_PROMPT
from schemas.documents import DocumentExtraction, UnknownDocumentExtraction

from .bank_statement import parse_bank_statement
from .deed import parse_deed
from .will import parse_will


LOGGER = logging.getLogger(__name__)

# Types we can turn into structured estate facts. Claude/keyword content detection
# is authoritative for these; everything else is filed by label only.
PARSEABLE_TYPES = ("will", "bank_statement", "deed")

# Aliases used to fuzzy-match a document's filename ("the title"). Ordered most- to
# least-distinctive so the first type wins on a score tie. Keep the alias phrases
# short and human — they are matched against a normalized filename, not body text.
TYPE_ALIASES: dict[str, list[str]] = {
    "death_certificate": ["death certificate", "certificate of death", "death cert"],
    "letters_testamentary": ["letters testamentary", "letters of administration", "letters"],
    "de160_inventory": ["de160", "de 160", "inventory and appraisal", "inventory appraisal", "inventory"],
    "creditor_notice": ["creditor notice", "notice to creditors", "creditor claim", "creditor"],
    "debt_payment_receipt": ["debt payment receipt", "payment receipt", "debt payment", "payment confirmation"],
    "distribution_receipt": ["distribution receipt", "distribution"],
    "mortgage_statement": ["mortgage statement", "mortgage", "loan statement"],
    "vehicle_title": ["vehicle title", "car title", "certificate of title", "pink slip"],
    "tax_return": ["tax return", "form 1040", "1040", "income tax"],
    "insurance_policy": ["insurance policy", "life insurance", "insurance", "policy"],
    "bank_statement": ["bank statement", "brokerage statement", "account statement", "statement"],
    "deed": ["grant deed", "quitclaim deed", "property deed", "deed"],
    "will": ["last will and testament", "last will", "living trust", "will", "testament", "trust"],
}

# Minimum average token similarity for a fuzzy filename match to count.
_FILENAME_MATCH_THRESHOLD = 0.82


async def parse_document_text(
    text: str,
    filename: str = "",
    forced_type: str | None = None,
) -> tuple[DocumentExtraction, str]:
    """Parse a document, returning the extraction and the resolved document type.

    The resolved type is the user's manual choice when given, otherwise the result
    of auto-detection (content + fuzzy filename matching). It is the label the
    caller should store the document under.
    """
    document_type = forced_type or resolve_document_type(text, filename)
    with span(
        "documents.parse",
        action_type="document_parse",
        doc_type=document_type,
        input_length=len(text),
        filename=filename,
    ) as current_span:
        if document_type == "will":
            extraction: DocumentExtraction = await parse_will(text)
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
        return extraction, document_type


def resolve_document_type(text: str, filename: str = "") -> str:
    """Best-effort document type from content and the filename.

    Content detection wins for the structured types we can parse; otherwise we fall
    back to fuzzy filename matching, then alias keywords in the body text.
    """
    primary = _detect_type(text)
    if primary in PARSEABLE_TYPES:
        return primary

    by_name = detect_type_from_filename(filename)
    if by_name:
        return by_name

    return _detect_by_aliases(text.lower()) or "unknown"


def detect_document_type(text: str) -> str:
    return _keyword_detect(text)


def detect_type_from_filename(filename: str) -> str | None:
    """Fuzzy-match a filename against known document types.

    Strips the extension and any numbering/separators ("03_death_certificate.pdf" →
    "death certificate"), then scores each alias both by substring containment and
    token-level similarity so typos ("deth certifcate") still resolve.
    """
    normalized = re.sub(r"[^a-z]+", " ", filename.lower()).strip()
    if not normalized:
        return None

    words = normalized.split()
    best_type: str | None = None
    best_score = 0.0
    for dtype, aliases in TYPE_ALIASES.items():
        for alias in aliases:
            score = 1.0 if alias in normalized else _token_similarity(alias, words)
            if score > best_score:
                best_score, best_type = score, dtype

    return best_type if best_score >= _FILENAME_MATCH_THRESHOLD else None


def _token_similarity(alias: str, words: list[str]) -> float:
    """Average best-match similarity of each alias word against the filename words."""
    alias_words = alias.split()
    if not alias_words or not words:
        return 0.0
    total = 0.0
    for alias_word in alias_words:
        total += max(difflib.SequenceMatcher(None, alias_word, word).ratio() for word in words)
    return total / len(alias_words)


def _detect_by_aliases(haystack: str) -> str | None:
    """Match alias phrases anywhere in the lowercased body text."""
    for dtype, aliases in TYPE_ALIASES.items():
        if any(alias in haystack for alias in aliases):
            return dtype
    return None


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
        if label in PARSEABLE_TYPES:
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
