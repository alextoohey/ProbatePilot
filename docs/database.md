# Database Contract

ClearPath uses Redis as the shared database for the hackathon:

- Redis KV stores canonical estate state.
- Redis vector search stores embedded document chunks for RAG and agent memory.
- The rest of the app must access Redis only through `agent/store/redis_client.py`.

The current implementation is an in-memory fallback with the same function names. This
lets every member build against stable contracts before Redis credentials and vector index
setup are complete.

## Ownership

Member 2 owns this contract and the Redis implementation. Other members should import the
helpers from `agent/store/redis_client.py` instead of creating Redis clients directly.

## Keys

| Data | Key / Index | Shape |
|------|-------------|-------|
| Estate state | `estate:{estateId}` | JSON serialized `EstateState` |
| Alerts | inside `estate:{estateId}.alerts` | `Alert[]` |
| Document chunk vectors | `estate_chunks` vector index | chunk text + metadata |

## Vector Metadata

Each embedded chunk should store:

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

If the implementation changes from memory to Upstash or Redis Cloud, these signatures
should stay stable.

## Redis Implementation Checklist

Before the demo, Member 2 should replace the in-memory implementation with real Redis:

1. Pick one Redis provider: Upstash or Redis Cloud.
2. Create the `estate_chunks` vector index using the embedding dimension from the real
   embedding model.
3. Store `EstateState` as JSON at `estate:{estateId}`.
4. Validate every read back through Pydantic before returning it.
5. Implement vector upsert with `estateId`, `source`, `documentType`, and `chunkIndex`
   metadata.
6. Implement semantic search with an explicit `estateId` filter.
7. Keep `/seed` idempotent: it should reset `demo-milligan` to the known demo state.
8. Add one integration check: seed, read estate, upsert chunks, search by estate ID.

## Environment

`agent/.env.example` lists both Upstash Redis REST and Upstash Vector variables. If the
team uses Redis Cloud instead, keep the provider-specific connection details inside
`agent/store/redis_client.py` so callers do not change.

