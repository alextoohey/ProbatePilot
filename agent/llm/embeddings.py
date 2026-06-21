from __future__ import annotations

import hashlib

from observability.arize import set_span_attribute, span


VECTOR_SIZE = 16


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic local embedding placeholder.

    Member 1 can replace this implementation with OpenAI text-embedding-3-small while
    preserving the function signature used by chat, documents, and storage.
    """
    with span(
        "embeddings.embed_texts",
        action_type="document_parse",
        llm_provider="openai",
        llm_model="text-embedding-3-small",
        text_count=len(texts),
        vector_size=VECTOR_SIZE,
    ) as current_span:
        vectors = [_embed_one(text) for text in texts]
        set_span_attribute(current_span, "embedding_count", len(vectors))
        return vectors


def embed_query(text: str) -> list[float]:
    with span(
        "embeddings.embed_query",
        action_type="chat_query",
        llm_provider="openai",
        llm_model="text-embedding-3-small",
        message_length=len(text),
        vector_size=VECTOR_SIZE,
    ):
        return _embed_one(text)


def _embed_one(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [((digest[index] / 255) * 2) - 1 for index in range(VECTOR_SIZE)]
