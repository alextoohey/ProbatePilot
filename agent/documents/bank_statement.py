from __future__ import annotations

import re

from llm.claude import structured_extract
from prompts.extraction import BANK_STATEMENT_EXTRACTION_PROMPT
from schemas.documents import BankStatementExtraction


async def parse_bank_statement(text: str) -> BankStatementExtraction:
    return await structured_extract(
        prompt=BANK_STATEMENT_EXTRACTION_PROMPT,
        content=text,
        response_model=BankStatementExtraction,
        fallback={
            "documentType": "bank_statement",
            "confidence": 0.55,
            "institution": "Wells Fargo" if "wells fargo" in text.lower() else None,
            "accountLast4": _find_last4(text),
            "accountType": "checking" if "checking" in text.lower() else None,
            "rawChunks": _emergency_chunks(text),
        },
    )


def _find_last4(text: str) -> str | None:
    match = re.search(r"(?:account|acct)[^\d]*(\d{4})", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _emergency_chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    return [cleaned[:500]] if cleaned else []
