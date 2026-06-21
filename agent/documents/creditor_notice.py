from __future__ import annotations

from llm.claude import structured_extract
from prompts.extraction import CREDITOR_NOTICE_EXTRACTION_PROMPT
from schemas.documents import CreditorNoticeExtraction


async def parse_creditor_notice(text: str) -> CreditorNoticeExtraction:
    return await structured_extract(
        prompt=CREDITOR_NOTICE_EXTRACTION_PROMPT,
        content=text,
        response_model=CreditorNoticeExtraction,
        allow_fallback=True,
        fallback={
            "documentType": "creditor_notice",
            "confidence": 0.5,
            "creditorName": None,
            "amountOwed": None,
            "accountNumber": None,
            "debtType": "unsecured",
            "debts": [],
            "rawChunks": [text[:500]] if text.strip() else [],
        },
    )
