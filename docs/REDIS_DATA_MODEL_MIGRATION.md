# Estate storage: whole-blob strings → RedisJSON — scoped, not built

**Status:** not started. This is a scoping document for future work, written so it can be
picked up without re-deriving any of the research below. `agent/store/` is untouched — it
still stores each estate as one JSON string, described below.

## Why this exists

Every `EstateState` is stored as a single Redis string: `estate:{id}` → the whole object,
`model_dump_json()`-encoded (`agent/store/redis_client.py`'s `set_estate_state()`), read
back with a plain `GET` + Pydantic validation (`get_estate_state()`). Every partial update —
completing one task, dismissing one alert, adding one document — goes through
`merge_estate_state()` (`redis_client.py:404`), which does a full read, applies the partial
dict in Python, and writes the *entire* object back. There is no field-level write.

This is a legitimate, common pattern for document-shaped data, and it fits how the app
actually reads it: the dashboard, chat prompt builder, and DeadlineAgent all want the *whole*
estate at once, so whole-object access is the common case, not the exception. It is not a
performance problem at this app's actual scale — a full estate is ~14KB (verified against a
live Redis Cloud instance this session), so a full read-modify-write costs nothing
measurable. This migration is about modeling the data the way Redis is actually designed for
nested documents, not about fixing a real bottleneck — worth being honest about that framing
rather than overselling it as a fix.

## The better approach: RedisJSON path-level operations

The Redis Cloud instance this app runs on already has the `ReJSON` module loaded (confirmed
via `MODULE LIST` this session, alongside `search`, `vectorset`, `bf`, and `timeseries` — the
standard Redis 8 module bundle). RedisJSON stores genuinely nested JSON natively and supports
path-level commands: `JSON.SET estate:{id} $.tasks[3].completed true`,
`JSON.NUMINCRBY estate:{id} $.someCounter 1`, array-append operations, and so on — a single
targeted write instead of get-full → modify-in-Python → set-full.

## Architecture notes for whoever builds this

1. **This is Redis-Cloud-specific, and that's a real conflict with an existing design
   goal.** `store/backends/kv.py`'s docstring is explicit that the `KVStore` Protocol exists
   so `memory`, `upstash`, and `redis_cloud` all "reduce to get/set/delete/scan on string
   keys" — one uniform interface, no backend-specific branching in the domain layer. Upstash
   has its own separate JSON product with a different REST call shape, and the in-memory
   backend has no concept of JSON paths at all. Adding `JSON.SET`-style path operations
   naively would break that uniformity. The design question to solve first: extend the
   `KVStore` Protocol with optional path-level methods that `redis_cloud` implements
   natively and the other two backends emulate via the existing full-blob get/modify/set
   (functionally identical result, just not the faster path) — not special-case
   `redis_client.py` itself per backend.
2. **`merge_estate_state()` is already the single choke point.** Every partial update
   already funnels through this one function — the natural migration is to change *its*
   internals to issue path-level writes when the active backend is `redis_cloud`, not to
   touch every call site that calls it today.
3. **Vector storage is a separate, already-solved concern.** Chunk embeddings use native
   Vector Sets via their own backend file (`store/backends/redis_cloud_vectors.py`) — this
   migration is about the KV/estate-document side only.
4. **Testing**: needs `redis_cloud`-specific coverage for the new path operations (the
   `memory`/`upstash` paths would still exercise the existing full-blob emulation, so
   existing tests there stay valid). Same mocking pattern as the rest of `agent/tests/`.

## Rough effort estimate

~2-3 hours: `KVStore` Protocol extension + `redis_cloud` path-op implementation + full-blob
emulation fallback for the other two backends + `merge_estate_state()` rewire + tests. Not a
large change, but a real design decision (protocol shape) that deserves its own focused pass
rather than being folded into an unrelated change.
