from __future__ import annotations

import hashlib
import os

import openai

EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI()
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not os.getenv("OPENAI_API_KEY"):
        return [_embed_one(text) for text in texts]
    try:
        response = _get_client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception as exc:
        print(f"[embeddings] OpenAI embedding failed, using deterministic fallback: {exc}")
        return [_embed_one(text) for text in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _embed_one(text: str) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < VECTOR_SIZE:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        values.extend(((byte / 255) * 2) - 1 for byte in digest)
        counter += 1
    return values[:VECTOR_SIZE]
