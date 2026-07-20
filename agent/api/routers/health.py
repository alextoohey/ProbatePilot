from __future__ import annotations

from fastapi import APIRouter

from observability.phoenix import get_tracing_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "tracing": get_tracing_status()}
