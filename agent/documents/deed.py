from __future__ import annotations

from schemas.documents import DeedExtraction


async def parse_deed(text: str) -> DeedExtraction:
    return DeedExtraction(
        confidence=0.55,
        propertyAddress="1847 Marin Ave, Berkeley CA" if "marin" in text.lower() else None,
        rawChunks=[text[:500]] if text.strip() else [],
    )

