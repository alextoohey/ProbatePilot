from __future__ import annotations

import hashlib
import logging
import os

import openai
from observability.phoenix import set_span_attribute, set_span_error, span

EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
LOGGER = logging.getLogger(__name__)

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI()
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    with span(
        "embeddings.embed_texts",
        action_type="document_parse",
        llm_provider="openai",
        llm_model=EMBEDDING_MODEL,
        text_count=len(texts),
        vector_size=VECTOR_SIZE,
    ) as current_span:
        if not os.getenv("OPENAI_API_KEY"):
            set_span_attribute(current_span, "fallback_used", True)
            set_span_attribute(current_span, "fallback_reason", "missing_openai_api_key")
            return [_embed_one(text) for text in texts]
        try:
            response = _get_client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
            embeddings = [item.embedding for item in response.data]
            set_span_attribute(current_span, "fallback_used", False)
            set_span_attribute(current_span, "fallback_reason", "")
            set_span_attribute(current_span, "embedding_count", len(embeddings))
            return embeddings
        except Exception as exc:
            set_span_error(current_span, exc)
            set_span_attribute(current_span, "fallback_used", True)
            set_span_attribute(current_span, "fallback_reason", f"{exc.__class__.__name__}: {str(exc)[:160]}")
            LOGGER.exception("OpenAI embedding failed; using deterministic fallback.")
            return [_embed_one(text) for text in texts]


def embed_query(text: str) -> list[float]:
    with span(
        "embeddings.embed_query",
        action_type="chat_query",
        llm_provider="openai",
        llm_model=EMBEDDING_MODEL,
        message_length=len(text),
        vector_size=VECTOR_SIZE,
    ):
        return embed_texts([text])[0]


def _embed_one(text: str) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < VECTOR_SIZE:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        values.extend(((byte / 255) * 2) - 1 for byte in digest)
        counter += 1
    return values[:VECTOR_SIZE]
