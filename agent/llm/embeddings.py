from __future__ import annotations

import hashlib
import logging
import os
import re
from math import sqrt

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


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _embed_one(text: str) -> list[float]:
    """Deterministic fallback used only when OPENAI_API_KEY is unset or the
    real embedding call fails. This is a hashing-trick bag-of-words vector
    (Weinberger et al.), not a real semantic embedding — it has no notion of
    synonyms or paraphrase. But unlike hashing the whole string as one blob
    (the previous approach), two texts that share words produce vectors that
    actually overlap in those hashed dimensions, so cosine similarity
    correlates with real lexical overlap instead of being pure noise. Each
    word hashes to one of VECTOR_SIZE buckets with a random +1/-1 sign (an
    unbiased estimator that reduces collision bias), and the result is
    L2-normalized so document length doesn't skew similarity scores."""
    vector = [0.0] * VECTOR_SIZE
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    norm = sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
