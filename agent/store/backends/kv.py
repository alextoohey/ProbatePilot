"""Uniform key-value interface over the three supported store backends.

Every domain function in `store.redis_client` (estates, users, sessions, chat
history, ...) reduces to get/set/delete/scan on string keys. Previously each
of those ~15 functions hand-wrote the same three-way
`if upstash / elif redis_cloud / else memory` branch. `KVStore` collects that
branch into one place per backend so the domain layer just calls
`_kv().get(key)`.

Values are always strings (JSON-encoded by the caller when the payload isn't
already a string) so the memory backend behaves identically to the two real
backends instead of holding live Python objects.
"""

from __future__ import annotations

import os
import time
from typing import Protocol


class KVStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ex: int | None = None) -> None: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def scan_keys(self, prefix: str) -> list[str]: ...


class MemoryKVStore:
    """In-process store for offline dev and tests. Matches the wire shape of
    the real backends (plain strings, optional TTL) rather than holding
    typed objects, so behavior doesn't drift between backends."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    def get(self, key: str) -> str | None:
        self._evict_if_expired(key)
        return self._data.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = value
        if ex is not None:
            self._expires_at[key] = time.monotonic() + ex
        else:
            self._expires_at.pop(key, None)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._expires_at.pop(key, None)

    def exists(self, key: str) -> bool:
        self._evict_if_expired(key)
        return key in self._data

    def scan_keys(self, prefix: str) -> list[str]:
        now = time.monotonic()
        live = [k for k, exp in self._expires_at.items() if exp <= now]
        for key in live:
            self.delete(key)
        return [key for key in self._data if key.startswith(prefix)]

    def reset(self) -> None:
        """Test-only: clear all state between test cases."""
        self._data.clear()
        self._expires_at.clear()

    def _evict_if_expired(self, key: str) -> None:
        expiry = self._expires_at.get(key)
        if expiry is not None and expiry <= time.monotonic():
            self.delete(key)


class UpstashKVStore:
    """Upstash Redis REST API."""

    def __init__(self) -> None:
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            try:
                from upstash_redis import Redis
            except ImportError as exc:
                raise RuntimeError("Install upstash-redis or set STORE_BACKEND=memory") from exc

            url = os.getenv("UPSTASH_REDIS_REST_URL")
            token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
            if not url or not token:
                raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required")
            self._client = Redis(url=url, token=token)
        return self._client

    def get(self, key: str) -> str | None:
        return self._client_or_raise().get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        if ex is not None:
            self._client_or_raise().set(key, value, ex=ex)
        else:
            self._client_or_raise().set(key, value)

    def delete(self, key: str) -> None:
        self._client_or_raise().delete(key)

    def exists(self, key: str) -> bool:
        return bool(self._client_or_raise().exists(key))

    def scan_keys(self, prefix: str) -> list[str]:
        return [str(key) for key in self._client_or_raise().keys(f"{prefix}*")]


class RedisCloudKVStore:
    """Redis Cloud (or any TLS-capable Redis 8 instance) via redis-py."""

    def __init__(self) -> None:
        self._client = None

    def client(self):
        """Exposed for vector backends that need raw `execute_command` access."""
        return self._client_or_raise()

    def _client_or_raise(self):
        if self._client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("Install redis or set STORE_BACKEND=memory") from exc

            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                raise RuntimeError("REDIS_URL is required when STORE_BACKEND=redis_cloud")

            self._client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=5.0,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        return self._client

    def get(self, key: str) -> str | None:
        return self._client_or_raise().get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._client_or_raise().set(key, value, ex=ex)

    def delete(self, key: str) -> None:
        self._client_or_raise().delete(key)

    def exists(self, key: str) -> bool:
        return bool(self._client_or_raise().exists(key))

    def scan_keys(self, prefix: str) -> list[str]:
        return [str(key) for key in self._client_or_raise().scan_iter(match=f"{prefix}*")]
