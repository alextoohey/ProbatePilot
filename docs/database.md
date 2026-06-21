# Database Contract

ClearPath uses Redis as the shared database for the hackathon:

- Redis KV stores canonical estate state.
- Redis vector search stores embedded document chunks for RAG and agent memory.
- The rest of the app must access Redis only through `agent/store/redis_client.py`.

The implementation supports three backends behind the same function names:

- `STORE_BACKEND=memory` — local in-memory KV + vector fallback for offline development.
- `STORE_BACKEND=redis_cloud` — Redis Cloud stores canonical estate KV and uses Redis 8
  Vector Sets (`VADD` / `VSIM`) for per-estate semantic retrieval.
- `STORE_BACKEND=upstash` — Upstash Redis REST for KV plus Upstash Vector for RAG chunks.

## Ownership

Member 2 owns this contract and the Redis implementation. Other members should import the
helpers from `agent/store/redis_client.py` instead of creating Redis clients directly.

## Keys

| Data | Key / Index | Shape |
|------|-------------|-------|
| Estate state | `estate:{estateId}` | JSON serialized `EstateState` |
| Alerts | inside `estate:{estateId}.alerts` | `Alert[]` |
| Document chunk vectors | `estate:{estateId}:chunks` | Redis Vector Set; chunk text/source stored as vector attributes |

## Vector Metadata

Each embedded chunk should store vector attributes:

```json
{
  "id": "demo-milligan:will.pdf:0",
  "estateId": "demo-milligan",
  "text": "Self-contained document chunk text...",
  "source": "will.pdf",
  "documentType": "will",
  "chunkIndex": 0
}
```

Search must always filter by `estateId`. Cross-estate retrieval is a correctness bug.
For the Redis Cloud backend, this is enforced by using one Vector Set per estate:
`estate:{estateId}:chunks`.

## Vector Dimensions

Production embeddings use OpenAI `text-embedding-3-small`, which returns **1536**
dimensions. Redis Vector Sets infer their dimension on first `VADD`, so the first vector
written to an estate set must be the same dimension as all future vectors for that estate.
If the embedding model changes, reset/rebuild that estate's vector set.

## Stable Store API

These functions are the boundary the rest of the app should rely on:

- `get_estate_state(estate_id)`
- `set_estate_state(estate)`
- `merge_estate_state(estate_id, partial)`
- `get_alerts(estate_id)`
- `write_alerts(estate_id, alerts)`
- `add_document(estate_id, document)`
- `upsert_vectors(estate_id, chunks, embeddings, source, document_type)`
- `semantic_search(estate_id, embedding, top_k)`
- `seed_demo_estate()`

If the implementation changes between memory, Upstash, or Redis Cloud, these signatures
should stay stable.

## Redis Implementation Checklist

Before the demo, Member 2 should replace the in-memory implementation with real Redis:

1. Pick one Redis provider: Upstash or Redis Cloud.
2. For Redis Cloud, confirm `VADD`, `VSIM`, and `VDIM` commands are available.
   For Upstash, create the Vector index using dimension `1536`.
3. Store `EstateState` as JSON at `estate:{estateId}`.
4. Validate every read back through Pydantic before returning it.
5. Implement vector upsert with `estateId`, `source`, `documentType`, and `chunkIndex`
   metadata/attributes.
6. Implement semantic search that cannot cross estates.
7. Keep `/seed` idempotent: it should reset `demo-milligan` to the known demo state.
8. Add one integration check: seed, read estate, upsert chunks, search by estate ID.

## Environment

`agent/.env.example` lists both Redis Cloud and Upstash variables. For Redis Cloud KV +
Vector Sets use:

```bash
STORE_BACKEND=redis_cloud
REDIS_URL=redis://default:<password>@<host>:<port>
```

Use `rediss://` instead of `redis://` when Redis Cloud requires TLS. The current Redis
Cloud path stores KV and vectors in the same database via Redis 8 Vector Sets. Upstash
still uses the `UPSTASH_*` REST variables.
