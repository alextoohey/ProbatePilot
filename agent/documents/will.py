from __future__ import annotations

from llm.claude import structured_extract
from prompts.extraction import WILL_EXTRACTION_PROMPT
from schemas.documents import WillExtraction


async def parse_will(text: str) -> WillExtraction:
    return await structured_extract(
        prompt=WILL_EXTRACTION_PROMPT,
        content=text,
        response_model=WillExtraction,
        fallback={"documentType": "will", "confidence": 0.0, "rawChunks": _emergency_chunks(text)},
    )


def _emergency_chunks(text: str) -> list[str]:
    """Fallback chunker used only if Claude call fails."""
    cleaned = " ".join(text.split())
    return [cleaned[i : i + 500] for i in range(0, min(len(cleaned), 2500), 500)]
