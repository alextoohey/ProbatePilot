from __future__ import annotations

import hashlib


VECTOR_SIZE = 1536


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic local embedding placeholder.

    Member 1 can replace this implementation with OpenAI text-embedding-3-small while
    preserving the function signature used by chat, documents, and storage.
    """
    return [_embed_one(text) for text in texts]


def embed_query(text: str) -> list[float]:
    return _embed_one(text)


def _embed_one(text: str) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < VECTOR_SIZE:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        values.extend(((byte / 255) * 2) - 1 for byte in digest)
        counter += 1
    return values[:VECTOR_SIZE]
