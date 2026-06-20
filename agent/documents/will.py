from __future__ import annotations

from schemas.documents import WillExtraction
from schemas.estate import Beneficiary


async def parse_will(text: str) -> WillExtraction:
    chunks = _chunks(text)
    return WillExtraction(
        confidence=0.55,
        executorName="Dana Milligan" if "dana" in text.lower() else None,
        beneficiaries=[Beneficiary(id="beneficiary-placeholder", name="Beneficiary from will")],
        specialInstructions=["Placeholder extraction. Replace with Claude structured parsing."],
        rawChunks=chunks,
    )


def _chunks(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    return [cleaned[:500]] if cleaned else []

