"""In-process vector store: a flat list plus brute-force cosine similarity.
Fine for demo-sized estates (dozens of chunks); not meant to scale."""

from __future__ import annotations

from math import sqrt
from typing import Any

from schemas.api import SearchResult


class MemoryVectorStore:
    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    def upsert(self, estate_id: str, rows: list[dict[str, Any]]) -> int:
        del estate_id  # rows already carry estateId; kept for interface parity
        for row in rows:
            self._rows[:] = [item for item in self._rows if item["id"] != row["id"]]
            self._rows.append(row)
        return len(rows)

    def search(self, estate_id: str, embedding: list[float], top_k: int) -> list[SearchResult]:
        matches = [item for item in self._rows if item["estateId"] == estate_id]
        ranked = sorted(matches, key=lambda item: _cosine_similarity(embedding, item["embedding"]), reverse=True)
        return [
            SearchResult(
                text=item["text"],
                score=_cosine_similarity(embedding, item["embedding"]),
                source=item["source"],
                documentType=item.get("documentType"),
                chunkIndex=item.get("chunkIndex"),
                estateId=item["estateId"],
            )
            for item in ranked[:top_k]
        ]

    def clear_estate(self, estate_id: str) -> int:
        before = len(self._rows)
        self._rows[:] = [item for item in self._rows if item["estateId"] != estate_id]
        return before - len(self._rows)

    def delete_source(self, estate_id: str, source: str, max_chunks: int = 100) -> int:
        del max_chunks  # memory backend scans the real row list; no id-guessing needed
        before = len(self._rows)
        self._rows[:] = [item for item in self._rows if not (item["estateId"] == estate_id and item.get("source") == source)]
        return before - len(self._rows)

    def reset(self) -> None:
        """Test-only: clear all state between test cases."""
        self._rows.clear()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
