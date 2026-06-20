from __future__ import annotations

import re

from schemas.documents import BankStatementExtraction


async def parse_bank_statement(text: str) -> BankStatementExtraction:
    last4 = _find_last4(text)
    return BankStatementExtraction(
        confidence=0.55,
        institution="Wells Fargo" if "wells fargo" in text.lower() else None,
        accountLast4=last4,
        accountType="checking" if "checking" in text.lower() else None,
        rawChunks=[text[:500]] if text.strip() else [],
    )


def _find_last4(text: str) -> str | None:
    match = re.search(r"(?:account|acct)[^\d]*(\d{4})", text, flags=re.IGNORECASE)
    return match.group(1) if match else None

