from __future__ import annotations

from llm.claude import structured_extract
from prompts.extraction import DEED_EXTRACTION_PROMPT
from schemas.documents import DeedExtraction


async def parse_deed(text: str) -> DeedExtraction:
    return await structured_extract(
        prompt=DEED_EXTRACTION_PROMPT,
        content=text,
        response_model=DeedExtraction,
        fallback={"documentType": "deed", "confidence": 0.0, "rawChunks": _emergency_chunks(text)},
    )


def _emergency_chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    return [cleaned[i : i + 500] for i in range(0, min(len(cleaned), 2500), 500)]
