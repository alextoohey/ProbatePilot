from __future__ import annotations

from llm.claude import structured_extract
from prompts.extraction import BANK_STATEMENT_EXTRACTION_PROMPT
from schemas.documents import BankStatementExtraction


async def parse_bank_statement(text: str) -> BankStatementExtraction:
    return await structured_extract(
        prompt=BANK_STATEMENT_EXTRACTION_PROMPT,
        content=text,
        response_model=BankStatementExtraction,
        fallback={"documentType": "bank_statement", "confidence": 0.0, "rawChunks": _emergency_chunks(text)},
    )


def _emergency_chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    return [cleaned[i : i + 500] for i in range(0, min(len(cleaned), 2500), 500)]
