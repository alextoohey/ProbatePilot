from __future__ import annotations

from copy import deepcopy
from math import sqrt
from typing import Any

from schemas.estate import Alert, EstateState, UploadedDocument, utc_now_iso
from seed.demo_estate import build_demo_estate


ESTATE_KEY_PREFIX = "estate:"
VECTOR_INDEX_NAME = "estate_chunks"
DEFAULT_ESTATE_ID = "demo-milligan"

_ESTATES: dict[str, EstateState] = {}
_VECTORS: list[dict[str, Any]] = []


def estate_key(estate_id: str) -> str:
    return f"{ESTATE_KEY_PREFIX}{estate_id}"


def seed_demo_estate() -> EstateState:
    estate = build_demo_estate()
    set_estate_state(estate)
    return estate


def get_estate_state(estate_id: str = DEFAULT_ESTATE_ID) -> EstateState:
    if estate_id not in _ESTATES and estate_id == DEFAULT_ESTATE_ID:
        return seed_demo_estate()
    return deepcopy(_ESTATES[estate_id])


def set_estate_state(estate: EstateState) -> EstateState:
    estate.updatedAt = utc_now_iso()
    _ESTATES[estate.id] = deepcopy(estate)
    return deepcopy(estate)


def merge_estate_state(estate_id: str, partial: dict[str, Any]) -> EstateState:
    estate = get_estate_state(estate_id)
    append_keys = {"assets", "debts", "beneficiaries", "documents", "tasks", "alerts"}

    for key, value in partial.items():
        if value is None:
            continue
        if key in append_keys:
            existing = list(getattr(estate, key))
            existing.extend(value)
            setattr(estate, key, existing)
        elif hasattr(estate, key):
            setattr(estate, key, value)

    return set_estate_state(EstateState.model_validate(estate.model_dump()))


def get_alerts(estate_id: str = DEFAULT_ESTATE_ID) -> list[Alert]:
    return get_estate_state(estate_id).alerts


def write_alerts(estate_id: str, alerts: list[Alert]) -> list[Alert]:
    estate = get_estate_state(estate_id)
    estate.alerts = alerts
    set_estate_state(estate)
    return alerts


def add_document(estate_id: str, document: UploadedDocument) -> EstateState:
    return merge_estate_state(estate_id, {"documents": [document]})


def upsert_vectors(
    estate_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    source: str | None = None,
    document_type: str | None = None,
) -> int:
    for index, chunk in enumerate(chunks):
        _VECTORS.append(
            {
                "id": chunk_id(estate_id, source, index),
                "estateId": estate_id,
                "text": chunk,
                "embedding": embeddings[index],
                "source": source,
                "documentType": document_type,
                "chunkIndex": index,
            }
        )
    return len(chunks)


def semantic_search(estate_id: str, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    matches = [item for item in _VECTORS if item["estateId"] == estate_id]
    ranked = sorted(matches, key=lambda item: _cosine_similarity(embedding, item["embedding"]), reverse=True)
    return [
        {
            "text": item["text"],
            "score": _cosine_similarity(embedding, item["embedding"]),
            "source": item["source"],
            "documentType": item.get("documentType"),
            "chunkIndex": item.get("chunkIndex"),
            "estateId": item["estateId"],
        }
        for item in ranked[:top_k]
    ]


def chunk_id(estate_id: str, source: str | None, chunk_index: int) -> str:
    return f"{estate_id}:{source or 'document'}:{chunk_index}"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
