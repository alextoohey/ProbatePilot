from __future__ import annotations

import hashlib


VECTOR_SIZE = 16


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic local embedding placeholder.

    Member 1 can replace this implementation with OpenAI text-embedding-3-small while
    preserving the function signature used by chat, documents, and storage.
    """
    return [_embed_one(text) for text in texts]


def embed_query(text: str) -> list[float]:
    return _embed_one(text)


def _embed_one(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [((digest[index] / 255) * 2) - 1 for index in range(VECTOR_SIZE)]

