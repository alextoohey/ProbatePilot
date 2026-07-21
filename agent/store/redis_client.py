"""Estate/user/session/chat/vector persistence — the domain layer.

This module owns key naming, JSON encode/decode, and Pydantic validation; it
delegates raw storage to a `KVStore` and vector search to a per-backend
vector store (see `store/backends/`). Which backend is active is selected via
`STORE_BACKEND` (`memory` | `upstash` | `redis_cloud`) and resolved once per
call through `_kv()` / `_vectors()`, so tests can flip backends with
`monkeypatch.setenv` between cases.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from constants import DEFAULT_ESTATE_ID, DEMO_VISITOR_TTL_SECONDS
from schemas.api import SearchResult
from schemas.auth import User
from schemas.estate import Alert, EstateState, Executor, SavedLetter, UploadedDocument, utc_now_iso
from seed.demo_estate import build_demo_estate
from store.backends.kv import MemoryKVStore, RedisCloudKVStore, UpstashKVStore
from store.backends.memory_vectors import MemoryVectorStore
from store.backends.redis_cloud_vectors import RedisCloudVectorStore

# Re-exported below (via `as`) purely so tests can exercise the redis_cloud
# parsing helpers directly as store.redis_client.X, matching this module's
# pre-refactor public surface; nothing in this file calls them itself.
from store.backends.redis_cloud_vectors import _ensure_redis_cloud_vector_dimension as _ensure_redis_cloud_vector_dimension
from store.backends.redis_cloud_vectors import _parse_redis_cloud_vector_matches as _parse_redis_cloud_vector_matches
from store.backends.redis_cloud_vectors import vector_set_key as vector_set_key
from store.backends.upstash_vectors import UpstashVectorStore, chunk_id

__all__ = [
    "seed_demo_estate",
    "get_chat_history",
    "append_chat_messages",
    "clear_chat_history",
    "list_chat_sessions",
    "create_chat_session",
    "get_chat_session_history",
    "append_chat_session_messages",
    "create_user",
    "get_user",
    "get_user_by_email",
    "update_user",
    "create_session",
    "get_session_user_id",
    "delete_session",
    "get_estate_state",
    "list_estate_ids",
    "set_estate_state",
    "merge_estate_state",
    "get_alerts",
    "write_alerts",
    "get_research_run_state",
    "set_research_run_state",
    "add_document",
    "delete_letter",
    "delete_document",
    "set_document_file",
    "delete_document_file",
    "get_document_file",
    "upsert_vectors",
    "semantic_search",
    "clear_estate_vectors",
    "delete_document_vectors",
    "chunk_id",
    "DEFAULT_ESTATE_ID",
]

ESTATE_KEY_PREFIX = "estate:"
USER_KEY_PREFIX = "user:"
USER_EMAIL_KEY_PREFIX = "user_email:"
SESSION_KEY_PREFIX = "session:"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
MAX_CHAT_MESSAGES = 200

_ENV_LOADED = False

# One instance per backend, created once. Each lazily opens its real client
# (Upstash REST / redis-py) on first use, so importing this module never
# requires network access or credentials.
_memory_kv = MemoryKVStore()
_upstash_kv = UpstashKVStore()
_redis_cloud_kv = RedisCloudKVStore()

_memory_vectors = MemoryVectorStore()
_upstash_vectors = UpstashVectorStore()
_redis_cloud_vectors = RedisCloudVectorStore(_redis_cloud_kv)


def reset_state() -> None:
    """Test-only: clear in-memory state and drop cached client connections
    so each test starts from a clean, disconnected slate."""
    _memory_kv.reset()
    _memory_vectors.reset()
    _upstash_kv._client = None
    _redis_cloud_kv._client = None


def estate_key(estate_id: str) -> str:
    return f"{ESTATE_KEY_PREFIX}{estate_id}"


def user_key(user_id: str) -> str:
    return f"{USER_KEY_PREFIX}{user_id}"


def user_email_key(email: str) -> str:
    return f"{USER_EMAIL_KEY_PREFIX}{email.strip().lower()}"


def session_key(token: str) -> str:
    return f"{SESSION_KEY_PREFIX}{token}"


def document_file_key(estate_id: str, doc_id: str) -> str:
    return f"{estate_key(estate_id)}:file:{doc_id}"


def research_run_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:researcher"


def chat_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:chat"


def chat_sessions_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:chat_sessions"


def store_backend() -> str:
    _load_env_file()
    return os.getenv("STORE_BACKEND", "memory").strip().lower() or "memory"


def _kv():
    backend = store_backend()
    if backend == "upstash":
        return _upstash_kv
    if backend == "redis_cloud":
        return _redis_cloud_kv
    return _memory_kv


def _vectors():
    backend = store_backend()
    if backend == "upstash":
        return _upstash_vectors
    if backend == "redis_cloud":
        return _redis_cloud_vectors
    return _memory_vectors


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
    return _decode_chat(_kv().get(chat_key(estate_id)))


def append_chat_messages(estate_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history = get_chat_history(estate_id)
    history.extend(messages)
    if len(history) > MAX_CHAT_MESSAGES:
        history = history[-MAX_CHAT_MESSAGES:]
    _kv().set(chat_key(estate_id), json.dumps(history))
    return history


def clear_chat_history(estate_id: str) -> None:
    _kv().delete(chat_key(estate_id))
    _kv().delete(chat_sessions_key(estate_id))


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
    return _decode_chat_sessions(_kv().get(chat_sessions_key(estate_id)), estate_id)


def _set_chat_sessions_raw(estate_id: str, sessions: list[dict[str, Any]]) -> None:
    _kv().set(chat_sessions_key(estate_id), json.dumps(sessions))


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
        _kv().set(chat_key(estate_id), json.dumps(history))
    return str(session.get("id")), history


# --------------------------------------------------------------------------- #
# Users & sessions (same store as estate state)
# --------------------------------------------------------------------------- #


def create_user(user: User, ttl_seconds: int | None = None) -> User:
    """Persist a new user and its email -> id index. Caller must ensure the
    email is not already taken (use ``get_user_by_email`` first). ``ttl_seconds``
    lets ephemeral records (e.g. per-visitor demo users) self-expire."""
    user = User.model_validate(_plain(user))
    _kv().set(user_key(user.id), user.model_dump_json(), ex=ttl_seconds)
    _kv().set(user_email_key(user.email), user.id, ex=ttl_seconds)
    return user


def get_user(user_id: str) -> User | None:
    raw = _kv().get(user_key(user_id))
    return _validate_user(raw) if raw is not None else None


def get_user_by_email(email: str) -> User | None:
    user_id = _kv().get(user_email_key(email))
    return get_user(user_id) if user_id else None


def update_user(user: User) -> User:
    """Overwrite an existing user record (e.g. to append an estate id)."""
    return create_user(user)


def create_session(user_id: str, token: str, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    _kv().set(session_key(token), user_id, ex=ttl_seconds)
    return token


def get_session_user_id(token: str) -> str | None:
    if not token:
        return None
    return _kv().get(session_key(token))


def delete_session(token: str) -> None:
    if not token:
        return
    _kv().delete(session_key(token))


def get_estate_state(estate_id: str = DEFAULT_ESTATE_ID) -> EstateState:
    """Raises KeyError if the estate doesn't exist (except the demo estate,
    which is lazily seeded on first read so a fresh deploy always has
    something to show)."""
    raw = _kv().get(estate_key(estate_id))
    if raw is None:
        if estate_id == DEFAULT_ESTATE_ID:
            return seed_demo_estate()
        raise KeyError(f"Estate state not found: {estate_id}")
    return _validate_estate(raw)


def list_estate_ids() -> list[str]:
    keys = _kv().scan_keys(ESTATE_KEY_PREFIX)
    return sorted(_estate_id_from_key(key) for key in keys if _is_estate_state_key(str(key)))


def set_estate_state(estate: EstateState | dict[str, Any], ttl_seconds: int | None = None) -> EstateState:
    estate = EstateState.model_validate(_plain(estate))
    estate.updatedAt = utc_now_iso()
    estate = EstateState.model_validate(estate.model_dump())
    # A plain SET clears any existing TTL, so every write to a per-visitor demo
    # estate must reapply one or it becomes permanent after its first edit.
    # Renewing it here (rather than requiring every caller to pass ttl_seconds)
    # also gives active demo sessions a sliding expiry instead of a hard cutoff.
    if ttl_seconds is None and estate.isDemo:
        ttl_seconds = DEMO_VISITOR_TTL_SECONDS
    _kv().set(estate_key(estate.id), estate.model_dump_json(), ex=ttl_seconds)
    return estate


def merge_estate_state(estate_id: str, partial: dict[str, Any]) -> EstateState:
    try:
        estate = get_estate_state(estate_id)
    except KeyError:
        estate = _blank_estate_state(estate_id, partial)

    append_keys = {"assets", "debts", "beneficiaries", "documents", "tasks", "alerts", "letters"}
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


def get_research_run_state(estate_id: str) -> dict[str, Any]:
    raw = _kv().get(research_run_key(estate_id))
    return json.loads(raw) if raw else {}


def set_research_run_state(estate_id: str, state: dict[str, Any]) -> dict[str, Any]:
    payload = _plain(state)
    _kv().set(research_run_key(estate_id), json.dumps(payload))
    return payload


def add_document(estate_id: str, document: UploadedDocument) -> EstateState:
    return merge_estate_state(estate_id, {"documents": [document]})


def delete_letter(estate_id: str, letter_id: str) -> SavedLetter | None:
    try:
        estate = get_estate_state(estate_id)
    except KeyError:
        return None
    letter = next((item for item in estate.letters if item.id == letter_id), None)
    if letter is None:
        return None
    estate.letters = [item for item in estate.letters if item.id != letter_id]
    set_estate_state(estate)
    return letter


def delete_document(estate_id: str, doc_id: str) -> UploadedDocument | None:
    try:
        estate = get_estate_state(estate_id)
    except KeyError:
        return None
    document = next((doc for doc in estate.documents if doc.id == doc_id), None)
    if document is None:
        return None

    estate.documents = [doc for doc in estate.documents if doc.id != doc_id]
    set_estate_state(estate)
    delete_document_file(estate_id, doc_id)
    try:
        delete_document_vectors(estate_id, document.fileName)
    except Exception:
        # The file and estate metadata are the source of truth for deletion. Vector
        # cleanup is best-effort because providers differ in delete/list support.
        pass
    return document


def set_document_file(estate_id: str, doc_id: str, content_type: str, data: bytes) -> None:
    """Store the original uploaded bytes so the UI can preview/download the real
    file. Persisted as base64 JSON alongside its content type."""
    record = json.dumps({"contentType": content_type, "data": base64.b64encode(data).decode("ascii")})
    _kv().set(document_file_key(estate_id, doc_id), record)


def delete_document_file(estate_id: str, doc_id: str) -> None:
    _kv().delete(document_file_key(estate_id, doc_id))


def get_document_file(estate_id: str, doc_id: str) -> dict[str, Any] | None:
    """Return ``{"contentType": str, "data": bytes}`` or None if not stored."""
    return _decode_document_file(_kv().get(document_file_key(estate_id, doc_id)))


def _decode_document_file(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    payload = json.loads(raw) if isinstance(raw, str) else raw
    return {
        "contentType": payload.get("contentType", "application/octet-stream"),
        "data": base64.b64decode(payload["data"]),
    }


# --------------------------------------------------------------------------- #
# Vector search
# --------------------------------------------------------------------------- #


def upsert_vectors(
    estate_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    source: str | None = None,
    document_type: str | None = None,
) -> int:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    rows = [
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

    return _vectors().upsert(estate_id, rows)


def semantic_search(estate_id: str, embedding: list[float], top_k: int = 5) -> list[SearchResult]:
    return _vectors().search(estate_id, embedding, top_k)


def clear_estate_vectors(estate_id: str) -> int:
    return _vectors().clear_estate(estate_id)


def delete_document_vectors(estate_id: str, source: str, max_chunks: int = 100) -> int:
    return _vectors().delete_source(estate_id, source, max_chunks)


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


def _is_estate_state_key(key: str) -> bool:
    suffix = key.removeprefix(ESTATE_KEY_PREFIX)
    return bool(suffix) and ":" not in suffix


def _estate_id_from_key(key: Any) -> str:
    if isinstance(key, bytes):
        key = key.decode("utf-8")
    return str(key).removeprefix(ESTATE_KEY_PREFIX)


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
