from __future__ import annotations

import base64
import json
import os
import uuid
from copy import deepcopy
from datetime import date
from math import sqrt
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from schemas.api import SearchResult
from schemas.auth import User
from schemas.estate import Alert, EstateState, Executor, UploadedDocument, utc_now_iso
from seed.demo_estate import build_demo_estate


ESTATE_KEY_PREFIX = "estate:"
USER_KEY_PREFIX = "user:"
USER_EMAIL_KEY_PREFIX = "user_email:"
SESSION_KEY_PREFIX = "session:"
VECTOR_INDEX_NAME = "estate_chunks"
DEFAULT_ESTATE_ID = "demo-milligan"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

_ESTATES: dict[str, EstateState] = {}
_CHATS: dict[str, list[dict[str, Any]]] = {}
_CHAT_SESSIONS: dict[str, list[dict[str, Any]]] = {}
MAX_CHAT_MESSAGES = 200
_VECTORS: list[dict[str, Any]] = []
_USERS: dict[str, User] = {}
_USER_EMAILS: dict[str, str] = {}
_SESSIONS: dict[str, str] = {}
_DOC_FILES: dict[str, dict[str, Any]] = {}
_REDIS_CLIENT: Any | None = None
_REDIS_CLOUD_CLIENT: Any | None = None
_VECTOR_CLIENT: Any | None = None
_ENV_LOADED = False


def estate_key(estate_id: str) -> str:
    return f"{ESTATE_KEY_PREFIX}{estate_id}"


def vector_set_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:chunks"


def user_key(user_id: str) -> str:
    return f"{USER_KEY_PREFIX}{user_id}"


def user_email_key(email: str) -> str:
    return f"{USER_EMAIL_KEY_PREFIX}{email.strip().lower()}"


def session_key(token: str) -> str:
    return f"{SESSION_KEY_PREFIX}{token}"


def document_file_key(estate_id: str, doc_id: str) -> str:
    return f"{estate_key(estate_id)}:file:{doc_id}"


def chat_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:chat"


def chat_sessions_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:chat_sessions"


def store_backend() -> str:
    _load_env_file()
    return os.getenv("STORE_BACKEND", "memory").strip().lower() or "memory"


def seed_demo_estate() -> EstateState:
    estate = build_demo_estate()
    clear_estate_vectors(estate.id)
    clear_chat_history(estate.id)
    return set_estate_state(estate)


# --------------------------------------------------------------------------- #
# Chat history (persisted per estate alongside estate state)
# --------------------------------------------------------------------------- #


def _decode_chat(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        data = raw
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def get_chat_history(estate_id: str) -> list[dict[str, Any]]:
    if _use_upstash():
        return _decode_chat(_redis().get(chat_key(estate_id)))
    if _use_redis_cloud():
        return _decode_chat(_redis_cloud().get(chat_key(estate_id)))
    return deepcopy(_CHATS.get(estate_id, []))


def append_chat_messages(estate_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history = get_chat_history(estate_id)
    history.extend(messages)
    if len(history) > MAX_CHAT_MESSAGES:
        history = history[-MAX_CHAT_MESSAGES:]

    if _use_upstash():
        _redis().set(chat_key(estate_id), json.dumps(history))
    elif _use_redis_cloud():
        _redis_cloud().set(chat_key(estate_id), json.dumps(history))
    else:
        _CHATS[estate_id] = deepcopy(history)
    return history


def clear_chat_history(estate_id: str) -> None:
    if _use_upstash():
        _redis().delete(chat_key(estate_id))
        _redis().delete(chat_sessions_key(estate_id))
    elif _use_redis_cloud():
        _redis_cloud().delete(chat_key(estate_id))
        _redis_cloud().delete(chat_sessions_key(estate_id))
    else:
        _CHATS.pop(estate_id, None)
        _CHAT_SESSIONS.pop(estate_id, None)


def _title_from_message(message: str) -> str:
    clean = " ".join(message.strip().split())
    if not clean:
        return "New chat"
    return clean if len(clean) <= 42 else f"{clean[:39].rstrip()}..."


def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    messages = _decode_chat(session.get("messages"))
    preview = next((m.get("content", "") for m in reversed(messages) if m.get("content")), None)
    return {
        "id": str(session.get("id", "")),
        "title": str(session.get("title") or "New chat"),
        "createdAt": str(session.get("createdAt") or utc_now_iso()),
        "updatedAt": str(session.get("updatedAt") or session.get("createdAt") or utc_now_iso()),
        "messageCount": len(messages),
        "preview": preview,
    }


def _decode_chat_sessions(raw: Any, estate_id: str) -> list[dict[str, Any]]:
    if raw is None:
        legacy = get_chat_history(estate_id)
        if not legacy:
            return []
        first_created = str(legacy[0].get("createdAt") or utc_now_iso())
        last_created = str(legacy[-1].get("createdAt") or first_created)
        first_user = next((m.get("content", "") for m in legacy if m.get("role") == "user"), "")
        return [{
            "id": "default",
            "title": _title_from_message(first_user) if first_user else "Estate chat",
            "createdAt": first_created,
            "updatedAt": last_created,
            "messages": legacy,
        }]
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        data = raw
    if not isinstance(data, list):
        return []
    return [s for s in data if isinstance(s, dict)]


def _get_chat_sessions_raw(estate_id: str) -> list[dict[str, Any]]:
    if _use_upstash():
        return _decode_chat_sessions(_redis().get(chat_sessions_key(estate_id)), estate_id)
    if _use_redis_cloud():
        return _decode_chat_sessions(_redis_cloud().get(chat_sessions_key(estate_id)), estate_id)
    raw = deepcopy(_CHAT_SESSIONS.get(estate_id))
    return _decode_chat_sessions(raw, estate_id)


def _set_chat_sessions_raw(estate_id: str, sessions: list[dict[str, Any]]) -> None:
    if _use_upstash():
        _redis().set(chat_sessions_key(estate_id), json.dumps(sessions))
    elif _use_redis_cloud():
        _redis_cloud().set(chat_sessions_key(estate_id), json.dumps(sessions))
    else:
        _CHAT_SESSIONS[estate_id] = deepcopy(sessions)


def list_chat_sessions(estate_id: str) -> list[dict[str, Any]]:
    sessions = [_session_summary(s) for s in _get_chat_sessions_raw(estate_id)]
    return sorted(sessions, key=lambda s: s.get("updatedAt", ""), reverse=True)


def create_chat_session(estate_id: str, title: str | None = None) -> dict[str, Any]:
    now = utc_now_iso()
    session = {
        "id": f"chat-{uuid.uuid4().hex[:10]}",
        "title": title or "New chat",
        "createdAt": now,
        "updatedAt": now,
        "messages": [],
    }
    sessions = _get_chat_sessions_raw(estate_id)
    sessions.append(session)
    _set_chat_sessions_raw(estate_id, sessions)
    return _session_summary(session)


def get_chat_session_history(estate_id: str, session_id: str | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    sessions = _get_chat_sessions_raw(estate_id)
    if not sessions:
        return None, []
    session = None
    if session_id:
        session = next((s for s in sessions if s.get("id") == session_id), None)
    if session is None:
        session = max(sessions, key=lambda s: str(s.get("updatedAt") or ""))
    return str(session.get("id")), _decode_chat(session.get("messages"))


def append_chat_session_messages(estate_id: str, session_id: str | None, messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    sessions = _get_chat_sessions_raw(estate_id)
    session = next((s for s in sessions if session_id and s.get("id") == session_id), None)
    if session is None:
        now = utc_now_iso()
        first_user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        session = {
            "id": session_id or f"chat-{uuid.uuid4().hex[:10]}",
            "title": _title_from_message(first_user),
            "createdAt": now,
            "updatedAt": now,
            "messages": [],
        }
        sessions.append(session)

    history = _decode_chat(session.get("messages"))
    history.extend(messages)
    if len(history) > MAX_CHAT_MESSAGES:
        history = history[-MAX_CHAT_MESSAGES:]
    if str(session.get("title") or "New chat") == "New chat":
        first_user = next((m.get("content", "") for m in history if m.get("role") == "user"), "")
        session["title"] = _title_from_message(first_user)
    session["messages"] = history
    session["updatedAt"] = str(messages[-1].get("createdAt") if messages else utc_now_iso())
    _set_chat_sessions_raw(estate_id, sessions)

    # Keep the original one-history key populated with the latest active chat for
    # older clients and tests that still call /chat-history without sessions.
    if not session_id or session.get("id") == session_id:
        if _use_upstash():
            _redis().set(chat_key(estate_id), json.dumps(history))
        elif _use_redis_cloud():
            _redis_cloud().set(chat_key(estate_id), json.dumps(history))
        else:
            _CHATS[estate_id] = deepcopy(history)
    return str(session.get("id")), history


# --------------------------------------------------------------------------- #
# Users & sessions (same Redis store as estate state)
# --------------------------------------------------------------------------- #


def create_user(user: User) -> User:
    """Persist a new user and its email -> id index. Caller must ensure the
    email is not already taken (use ``get_user_by_email`` first)."""
    user = User.model_validate(_plain(user))

    if _use_upstash():
        _redis().set(user_key(user.id), user.model_dump_json())
        _redis().set(user_email_key(user.email), user.id)
        return user

    if _use_redis_cloud():
        _redis_cloud().set(user_key(user.id), user.model_dump_json())
        _redis_cloud().set(user_email_key(user.email), user.id)
        return user

    _USERS[user.id] = deepcopy(user)
    _USER_EMAILS[user.email.strip().lower()] = user.id
    return deepcopy(user)


def get_user(user_id: str) -> User | None:
    if _use_upstash():
        raw = _redis().get(user_key(user_id))
        return _validate_user(raw) if raw is not None else None

    if _use_redis_cloud():
        raw = _redis_cloud().get(user_key(user_id))
        return _validate_user(raw) if raw is not None else None

    user = _USERS.get(user_id)
    return deepcopy(user) if user is not None else None


def get_user_by_email(email: str) -> User | None:
    normalized = email.strip().lower()

    if _use_upstash():
        user_id = _redis().get(user_email_key(normalized))
        return get_user(user_id) if user_id else None

    if _use_redis_cloud():
        user_id = _redis_cloud().get(user_email_key(normalized))
        return get_user(user_id) if user_id else None

    user_id = _USER_EMAILS.get(normalized)
    return get_user(user_id) if user_id else None


def update_user(user: User) -> User:
    """Overwrite an existing user record (e.g. to append an estate id)."""
    return create_user(user)


def create_session(user_id: str, token: str, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    if _use_upstash():
        _redis().set(session_key(token), user_id, ex=ttl_seconds)
        return token

    if _use_redis_cloud():
        _redis_cloud().set(session_key(token), user_id, ex=ttl_seconds)
        return token

    _SESSIONS[token] = user_id
    return token


def get_session_user_id(token: str) -> str | None:
    if not token:
        return None

    if _use_upstash():
        return _redis().get(session_key(token))

    if _use_redis_cloud():
        return _redis_cloud().get(session_key(token))

    return _SESSIONS.get(token)


def delete_session(token: str) -> None:
    if not token:
        return

    if _use_upstash():
        _redis().delete(session_key(token))
        return

    if _use_redis_cloud():
        _redis_cloud().delete(session_key(token))
        return

    _SESSIONS.pop(token, None)


def get_estate_state(estate_id: str = DEFAULT_ESTATE_ID) -> EstateState:
    if _use_upstash():
        raw_estate = _redis().get(estate_key(estate_id))
        if raw_estate is None and estate_id == DEFAULT_ESTATE_ID:
            return seed_demo_estate()
        if raw_estate is None:
            raise KeyError(f"Estate state not found: {estate_id}")
        return _validate_estate(raw_estate)

    if _use_redis_cloud():
        raw_estate = _redis_cloud().get(estate_key(estate_id))
        if raw_estate is None and estate_id == DEFAULT_ESTATE_ID:
            return seed_demo_estate()
        if raw_estate is None:
            raise KeyError(f"Estate state not found: {estate_id}")
        return _validate_estate(raw_estate)

    if estate_id not in _ESTATES and estate_id == DEFAULT_ESTATE_ID:
        return seed_demo_estate()
    if estate_id not in _ESTATES:
        raise KeyError(f"Estate state not found: {estate_id}")
    return deepcopy(_ESTATES[estate_id])


def set_estate_state(estate: EstateState | dict[str, Any]) -> EstateState:
    estate = EstateState.model_validate(_plain(estate))
    estate.updatedAt = utc_now_iso()
    estate = EstateState.model_validate(estate.model_dump())

    if _use_upstash():
        _redis().set(estate_key(estate.id), estate.model_dump_json())
        return estate

    if _use_redis_cloud():
        _redis_cloud().set(estate_key(estate.id), estate.model_dump_json())
        return estate

    _ESTATES[estate.id] = deepcopy(estate)
    return deepcopy(estate)


def merge_estate_state(estate_id: str, partial: dict[str, Any]) -> EstateState:
    try:
        estate = get_estate_state(estate_id)
    except KeyError:
        estate = _blank_estate_state(estate_id, partial)

    append_keys = {"assets", "debts", "beneficiaries", "documents", "tasks", "alerts"}
    estate_payload = estate.model_dump()

    for key, value in _plain(partial).items():
        if value is None:
            continue
        if key in append_keys:
            estate_payload[key] = _merge_list_by_id(estate_payload.get(key, []), value)
        elif isinstance(estate_payload.get(key), dict) and isinstance(value, dict):
            estate_payload[key] = _deep_merge_dict(estate_payload[key], value)
        elif key in estate_payload:
            estate_payload[key] = value

    return set_estate_state(EstateState.model_validate(estate_payload))


def get_alerts(estate_id: str = DEFAULT_ESTATE_ID) -> list[Alert]:
    return get_estate_state(estate_id).alerts


def write_alerts(estate_id: str, alerts: list[Alert | dict[str, Any]]) -> list[Alert]:
    estate = get_estate_state(estate_id)
    estate.alerts = [Alert.model_validate(_plain(alert)) for alert in alerts]
    set_estate_state(estate)
    return estate.alerts


def add_document(estate_id: str, document: UploadedDocument) -> EstateState:
    return merge_estate_state(estate_id, {"documents": [document]})


def set_document_file(estate_id: str, doc_id: str, content_type: str, data: bytes) -> None:
    """Store the original uploaded bytes so the UI can preview/download the real
    file. Persisted as base64 JSON alongside its content type."""
    record = json.dumps({"contentType": content_type, "data": base64.b64encode(data).decode("ascii")})
    key = document_file_key(estate_id, doc_id)

    if _use_upstash():
        _redis().set(key, record)
        return
    if _use_redis_cloud():
        _redis_cloud().set(key, record)
        return
    _DOC_FILES[key] = {"contentType": content_type, "data": data}


def get_document_file(estate_id: str, doc_id: str) -> dict[str, Any] | None:
    """Return ``{"contentType": str, "data": bytes}`` or None if not stored."""
    key = document_file_key(estate_id, doc_id)

    if _use_upstash():
        return _decode_document_file(_redis().get(key))
    if _use_redis_cloud():
        return _decode_document_file(_redis_cloud().get(key))

    record = _DOC_FILES.get(key)
    return deepcopy(record) if record is not None else None


def _decode_document_file(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    payload = json.loads(raw) if isinstance(raw, str) else raw
    return {
        "contentType": payload.get("contentType", "application/octet-stream"),
        "data": base64.b64decode(payload["data"]),
    }


def upsert_vectors(
    estate_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    source: str | None = None,
    document_type: str | None = None,
) -> int:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    vector_rows = [
        {
            "id": chunk_id(estate_id, source, index),
            "estateId": estate_id,
            "text": chunk,
            "embedding": embeddings[index],
            "source": source,
            "documentType": document_type,
            "chunkIndex": index,
        }
        for index, chunk in enumerate(chunks)
    ]

    if _use_upstash():
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
            for row in vector_rows
        ]
        if vectors:
            _vector().upsert(vectors=vectors)
        return len(vectors)

    if _use_redis_cloud():
        return _upsert_redis_cloud_vectors(estate_id, vector_rows)

    for index, _chunk in enumerate(chunks):
        vector_id = chunk_id(estate_id, source, index)
        _VECTORS[:] = [item for item in _VECTORS if item["id"] != vector_id]
        _VECTORS.append(vector_rows[index])
    return len(chunks)


def semantic_search(estate_id: str, embedding: list[float], top_k: int = 5) -> list[SearchResult]:
    if _use_upstash():
        query_result = _vector().query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter=f"estateId = '{estate_id}'",
        )
        matches = getattr(query_result, "matches", query_result)
        return [_search_result_from_upstash(match, estate_id) for match in matches]

    if _use_redis_cloud():
        return _semantic_search_redis_cloud(estate_id, embedding, top_k)

    matches = [item for item in _VECTORS if item["estateId"] == estate_id]
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


def clear_estate_vectors(estate_id: str) -> int:
    if _use_upstash():
        return 0

    if _use_redis_cloud():
        return int(_redis_cloud().delete(vector_set_key(estate_id)))

    before = len(_VECTORS)
    _VECTORS[:] = [item for item in _VECTORS if item["estateId"] != estate_id]
    return before - len(_VECTORS)


def chunk_id(estate_id: str, source: str | None, chunk_index: int) -> str:
    return f"{estate_id}:{source or 'document'}:{chunk_index}"


def _upsert_redis_cloud_vectors(estate_id: str, vector_rows: list[dict[str, Any]]) -> int:
    if not vector_rows:
        return 0

    redis_client = _redis_cloud()
    key = vector_set_key(estate_id)
    dimension = len(vector_rows[0]["embedding"])
    _ensure_redis_cloud_vector_dimension(redis_client, key, dimension)

    pipeline = redis_client.pipeline(transaction=False)
    for row in vector_rows:
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
    return len(vector_rows)


def _semantic_search_redis_cloud(estate_id: str, embedding: list[float], top_k: int) -> list[SearchResult]:
    if not embedding:
        return []

    key = vector_set_key(estate_id)
    if not _redis_cloud().exists(key):
        return []

    raw_matches = _redis_cloud().execute_command(
        "VSIM",
        key,
        "VALUES",
        len(embedding),
        *embedding,
        "WITHSCORES",
        "WITHATTRIBS",
        "COUNT",
        top_k,
    )
    return _parse_redis_cloud_vector_matches(raw_matches, estate_id)


def _ensure_redis_cloud_vector_dimension(redis_client: Any, key: str, dimension: int) -> None:
    if not redis_client.exists(key):
        return

    existing_dimension = int(redis_client.execute_command("VDIM", key))
    if existing_dimension != dimension:
        redis_client.delete(key)


def _parse_redis_cloud_vector_matches(raw_matches: Any, estate_id: str) -> list[SearchResult]:
    if isinstance(raw_matches, dict):
        return [
            _search_result_from_redis_cloud_attributes(score_and_attributes[0], score_and_attributes[1], estate_id)
            for score_and_attributes in raw_matches.values()
        ]

    results: list[SearchResult] = []
    index = 0
    while index < len(raw_matches):
        _element_id = raw_matches[index]
        score = float(raw_matches[index + 1])
        results.append(_search_result_from_redis_cloud_attributes(score, raw_matches[index + 2], estate_id))
        index += 3
    return results


def _search_result_from_redis_cloud_attributes(score: float, raw_attributes: str | None, estate_id: str) -> SearchResult:
    attributes = json.loads(raw_attributes or "{}")
    return SearchResult(
        text=attributes.get("text", ""),
        score=float(score),
        source=attributes.get("source"),
        documentType=attributes.get("documentType"),
        chunkIndex=attributes.get("chunkIndex"),
        estateId=attributes.get("estateId", estate_id),
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _use_upstash() -> bool:
    return store_backend() == "upstash"


def _use_redis_cloud() -> bool:
    return store_backend() == "redis_cloud"


def _redis() -> Any:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        try:
            from upstash_redis import Redis
        except ImportError as exc:
            raise RuntimeError("Install upstash-redis or set STORE_BACKEND=memory") from exc

        url = os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token:
            raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required")
        _REDIS_CLIENT = Redis(url=url, token=token)
    return _REDIS_CLIENT


def _redis_cloud() -> Any:
    global _REDIS_CLOUD_CLIENT
    if _REDIS_CLOUD_CLIENT is None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Install redis or set STORE_BACKEND=memory") from exc

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL is required when STORE_BACKEND=redis_cloud")

        _REDIS_CLOUD_CLIENT = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    return _REDIS_CLOUD_CLIENT


def _vector() -> Any:
    global _VECTOR_CLIENT
    if _VECTOR_CLIENT is None:
        try:
            from upstash_vector import Index
        except ImportError as exc:
            raise RuntimeError("Install upstash-vector or set STORE_BACKEND=memory") from exc

        url = os.getenv("UPSTASH_VECTOR_REST_URL")
        token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
        if not url or not token:
            raise RuntimeError("UPSTASH_VECTOR_REST_URL and UPSTASH_VECTOR_REST_TOKEN are required")
        _VECTOR_CLIENT = Index(url=url, token=token)
    return _VECTOR_CLIENT


def _load_env_file() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_file_without_dependency(env_path)
        return

    load_dotenv(env_path, override=False)


def _load_env_file_without_dependency(env_path: Path) -> None:
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _validate_estate(raw_estate: Any) -> EstateState:
    if isinstance(raw_estate, str):
        raw_estate = json.loads(raw_estate)
    return EstateState.model_validate(raw_estate)


def _validate_user(raw_user: Any) -> User:
    if isinstance(raw_user, str):
        raw_user = json.loads(raw_user)
    return User.model_validate(raw_user)


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _merge_list_by_id(existing: list[Any], incoming: list[Any]) -> list[Any]:
    merged = [_plain(item) for item in existing]
    positions = {item.get("id"): index for index, item in enumerate(merged) if isinstance(item, dict) and item.get("id")}

    for raw_item in _plain(incoming):
        if not isinstance(raw_item, dict) or not raw_item.get("id"):
            merged.append(raw_item)
            continue

        item_id = raw_item["id"]
        if item_id in positions:
            index = positions[item_id]
            merged[index] = _deep_merge_dict(merged[index], raw_item)
        else:
            positions[item_id] = len(merged)
            merged.append(raw_item)

    return merged


def _deep_merge_dict(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None:
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _blank_estate_state(estate_id: str, partial: dict[str, Any] | None = None) -> EstateState:
    partial = _plain(partial or {})
    today = date.today().isoformat()
    executor_payload = partial.get("executor") if isinstance(partial.get("executor"), dict) else {}
    return EstateState(
        id=estate_id,
        deceasedName=partial.get("deceasedName") or "Unknown Decedent",
        dateOfDeath=partial.get("dateOfDeath") or today,
        appointmentDate=partial.get("appointmentDate") or today,
        executor=Executor(
            name=executor_payload.get("name") or "Unknown Executor",
            email=executor_payload.get("email") or "",
        ),
        phase=partial.get("phase") or 1,
    )


def _search_result_from_upstash(match: Any, estate_id: str) -> SearchResult:
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
