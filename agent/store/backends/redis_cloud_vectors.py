"""Redis 8 Vector Sets on Redis Cloud, via raw VADD/VSIM/VDIM/VREM commands
(redis-py has no typed wrapper for these yet)."""

from __future__ import annotations

import json
from typing import Any

from schemas.api import SearchResult


class RedisCloudVectorStore:
    def __init__(self, kv_store) -> None:
        # Vector Sets share the same Redis connection as the KV store, so we
        # take the already-configured client rather than opening a second one.
        self._kv_store = kv_store

    def upsert(self, estate_id: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        client = self._kv_store.client()
        key = vector_set_key(estate_id)
        dimension = len(rows[0]["embedding"])
        _ensure_redis_cloud_vector_dimension(client, key, dimension)

        pipeline = client.pipeline(transaction=False)
        for row in rows:
            metadata = {
                "id": row["id"],
                "estateId": row["estateId"],
                "text": row["text"],
                "source": row["source"],
                "documentType": row["documentType"],
                "chunkIndex": row["chunkIndex"],
            }
            pipeline.execute_command(
                "VADD",
                key,
                "VALUES",
                len(row["embedding"]),
                *row["embedding"],
                row["id"],
                "SETATTR",
                json.dumps(metadata),
            )
        pipeline.execute()
        return len(rows)

    def search(self, estate_id: str, embedding: list[float], top_k: int) -> list[SearchResult]:
        if not embedding:
            return []

        client = self._kv_store.client()
        key = vector_set_key(estate_id)
        if not client.exists(key):
            return []

        raw_matches = client.execute_command(
            "VSIM", key, "VALUES", len(embedding), *embedding, "WITHSCORES", "WITHATTRIBS", "COUNT", top_k
        )
        return _parse_redis_cloud_vector_matches(raw_matches, estate_id)

    def clear_estate(self, estate_id: str) -> int:
        return int(self._kv_store.client().delete(vector_set_key(estate_id)))

    def delete_source(self, estate_id: str, source: str, max_chunks: int = 100) -> int:
        client = self._kv_store.client()
        key = vector_set_key(estate_id)
        removed = 0
        for index in range(max_chunks):
            removed += int(client.execute_command("VREM", key, chunk_id(estate_id, source, index)) or 0)
        return removed


def vector_set_key(estate_id: str) -> str:
    return f"estate:{estate_id}:chunks"


def chunk_id(estate_id: str, source: str | None, chunk_index: int) -> str:
    return f"{estate_id}:{source or 'document'}:{chunk_index}"


def _ensure_redis_cloud_vector_dimension(redis_client: Any, key: str, dimension: int) -> None:
    if not redis_client.exists(key):
        return

    existing_dimension = int(redis_client.execute_command("VDIM", key))
    if existing_dimension != dimension:
        redis_client.delete(key)


def _parse_redis_cloud_vector_matches(raw_matches: Any, estate_id: str) -> list[SearchResult]:
    if isinstance(raw_matches, dict):
        return [
            _row_from_attributes(score_and_attributes[0], score_and_attributes[1], estate_id)
            for score_and_attributes in raw_matches.values()
        ]

    results: list[SearchResult] = []
    index = 0
    while index < len(raw_matches):
        score = float(raw_matches[index + 1])
        results.append(_row_from_attributes(score, raw_matches[index + 2], estate_id))
        index += 3
    return results


def _row_from_attributes(score: float, raw_attributes: str | None, estate_id: str) -> SearchResult:
    attributes = json.loads(raw_attributes or "{}")
    return SearchResult(
        text=attributes.get("text", ""),
        score=float(score),
        source=attributes.get("source"),
        documentType=attributes.get("documentType"),
        chunkIndex=attributes.get("chunkIndex"),
        estateId=attributes.get("estateId", estate_id),
    )
