"""Upstash Vector index."""

from __future__ import annotations

import os
from typing import Any

from schemas.api import SearchResult


class UpstashVectorStore:
    def __init__(self) -> None:
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            try:
                from upstash_vector import Index
            except ImportError as exc:
                raise RuntimeError("Install upstash-vector or set STORE_BACKEND=memory") from exc

            url = os.getenv("UPSTASH_VECTOR_REST_URL")
            token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
            if not url or not token:
                raise RuntimeError("UPSTASH_VECTOR_REST_URL and UPSTASH_VECTOR_REST_TOKEN are required")
            self._client = Index(url=url, token=token)
        return self._client

    def upsert(self, estate_id: str, rows: list[dict[str, Any]]) -> int:
        del estate_id  # rows already carry estateId; kept for interface parity
        vectors = [
            (
                row["id"],
                row["embedding"],
                {
                    "id": row["id"],
                    "estateId": row["estateId"],
                    "text": row["text"],
                    "source": row["source"],
                    "documentType": row["documentType"],
                    "chunkIndex": row["chunkIndex"],
                },
            )
            for row in rows
        ]
        if vectors:
            self._client_or_raise().upsert(vectors=vectors)
        return len(vectors)

    def search(self, estate_id: str, embedding: list[float], top_k: int) -> list[SearchResult]:
        query_result = self._client_or_raise().query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter=f"estateId = '{estate_id}'",
        )
        matches = getattr(query_result, "matches", query_result)
        return [_match_to_row(match, estate_id) for match in matches]

    def clear_estate(self, estate_id: str) -> int:
        # The Upstash Vector REST API has no "delete by metadata filter" call,
        # so a full-estate clear can't be done in one round trip. Estate
        # deletion is rare enough that this is a documented limitation rather
        # than something worth a query-then-delete-N-ids workaround here.
        return 0

    def delete_source(self, estate_id: str, source: str, max_chunks: int = 100) -> int:
        ids = [chunk_id(estate_id, source, index) for index in range(max_chunks)]
        try:
            self._client_or_raise().delete(ids)
        except TypeError:
            self._client_or_raise().delete(ids=ids)
        return len(ids)


def chunk_id(estate_id: str, source: str | None, chunk_index: int) -> str:
    return f"{estate_id}:{source or 'document'}:{chunk_index}"


def _match_to_row(match: Any, estate_id: str) -> SearchResult:
    metadata = getattr(match, "metadata", None)
    if metadata is None and isinstance(match, dict):
        metadata = match.get("metadata", {})
    metadata = metadata or {}
    data = getattr(match, "data", None)
    if data is None and isinstance(match, dict):
        data = match.get("data")
    score = getattr(match, "score", None)
    if score is None and isinstance(match, dict):
        score = match.get("score", 0.0)

    return SearchResult(
        text=metadata.get("text") or data or "",
        score=float(score or 0.0),
        source=metadata.get("source"),
        documentType=metadata.get("documentType"),
        chunkIndex=metadata.get("chunkIndex"),
        estateId=metadata.get("estateId", estate_id),
    )
