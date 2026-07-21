"""Repo-wide constants with no dependencies of their own, so both the schema
layer and the store layer can import from here without a circular import
(store/redis_client.py imports from schemas/api.py, so schemas/api.py can't
import DEFAULT_ESTATE_ID back from the store)."""

from __future__ import annotations

DEFAULT_ESTATE_ID = "demo-milligan"

# Each "Try the demo" click gets its own isolated copy of the seed estate, so
# one visitor's edits (completed tasks, uploads) never leak into another's.
# Ephemeral by design — self-expires in the store rather than needing a
# cleanup job.
DEMO_VISITOR_TTL_SECONDS = 60 * 60 * 24  # 24 hours
