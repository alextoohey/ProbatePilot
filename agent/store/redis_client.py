from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date
from math import sqrt
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from schemas.api import SearchResult
from schemas.estate import Alert, EstateState, Executor, UploadedDocument, utc_now_iso
from seed.demo_estate import build_demo_estate


ESTATE_KEY_PREFIX = "estate:"
VECTOR_INDEX_NAME = "estate_chunks"
DEFAULT_ESTATE_ID = "demo-milligan"

_ESTATES: dict[str, EstateState] = {}
_VECTORS: list[dict[str, Any]] = []
_REDIS_CLIENT: Any | None = None
_REDIS_CLOUD_CLIENT: Any | None = None
_VECTOR_CLIENT: Any | None = None
_ENV_LOADED = False


def estate_key(estate_id: str) -> str:
    return f"{ESTATE_KEY_PREFIX}{estate_id}"


def vector_set_key(estate_id: str) -> str:
    return f"{estate_key(estate_id)}:chunks"


def store_backend() -> str:
    _load_env_file()
    return os.getenv("STORE_BACKEND", "memory").strip().lower() or "memory"


def seed_demo_estate() -> EstateState:
    estate = build_demo_estate()
    clear_estate_vectors(estate.id)
    return set_estate_state(estate)


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
