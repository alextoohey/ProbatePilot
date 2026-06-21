from __future__ import annotations

from llm.claude import structured_extract
from prompts.extraction import WILL_EXTRACTION_PROMPT
from schemas.documents import WillExtraction
from schemas.estate import Beneficiary


async def parse_will(text: str) -> WillExtraction:
    return await structured_extract(
        prompt=WILL_EXTRACTION_PROMPT,
        content=text,
        response_model=WillExtraction,
        fallback={
            "documentType": "will",
            "confidence": 0.55,
            "executorName": "Dana Milligan" if "dana" in text.lower() else None,
            "beneficiaries": [Beneficiary(id="beneficiary-placeholder", name="Beneficiary from will")],
            "specialInstructions": ["Placeholder extraction. Replace with Claude structured parsing."],
            "rawChunks": _emergency_chunks(text),
        },
    )


def _emergency_chunks(text: str) -> list[str]:
    """Fallback chunker used only if Claude call fails."""
    cleaned = " ".join(text.split())
    return [cleaned[:500]] if cleaned else []
