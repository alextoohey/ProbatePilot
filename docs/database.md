# Database Contract

ProbatePilot uses Redis as the shared database:

- Redis KV stores canonical estate state (and bcrypt-hashed accounts / sessions).
- Redis vector search stores embedded document chunks for RAG and agent memory.
- The rest of the app must access Redis only through `agent/store/redis_client.py`.

The implementation supports three interchangeable backends behind the same function names,
selected by `STORE_BACKEND`:

- `STORE_BACKEND=memory` — local in-memory KV + vector fallback for offline development
  (the `.env.example` default).
- `STORE_BACKEND=redis_cloud` — Redis Cloud stores canonical estate KV and uses Redis 8
  Vector Sets (`VADD` / `VSIM`) for per-estate semantic retrieval. This is the cloud path
  this project runs on.
- `STORE_BACKEND=upstash` — Upstash Redis REST for KV plus Upstash Vector for RAG chunks.
  Also supported.

Internally, `redis_client.py` is a thin domain layer (key naming, JSON encode/decode,
Pydantic validation) over `agent/store/backends/` — a `KVStore` implementation per backend
plus a separate vector-search implementation per backend, since Upstash's REST index and
Redis 8's `VADD`/`VSIM` commands don't share a common shape. Nothing outside `store/` should
import from `store/backends/` directly.

## What memory mode actually gives up

`STORE_BACKEND=memory` is a real, fully-working implementation, not a stub — every feature
works identically to the Redis-backed path, including semantic search (a brute-force
cosine-similarity scan; see `store/backends/memory_vectors.py`). The only thing it doesn't do
is survive the server process restarting: data lives in that process's RAM, so a crash, a
redeploy, or a host that spins down when idle (e.g. Render's free tier) wipes everything —
every account, every uploaded document, every estate. Fine for local dev in one sitting or a
quick clone-and-try; not fine for anything meant to hold real users' data reliably.

## Redis version requirement and what happens without it

Vector Sets (`VADD` / `VSIM` / `VDIM`) require **Redis 8+**. Pointing `REDIS_URL` at an
older or otherwise incompatible Redis doesn't break KV storage (estate state, accounts,
documents all still read/write fine with plain `GET`/`SET`) — it breaks semantic search
specifically:

- **Chat retrieval** already handles this: `api/routers/chat.py` wraps the vector search
  call in a try/except, so an unsupported-command error just disables retrieval for that
  message; chat continues without it.
- **Document upload** used to hard-fail with a 500 on the same error, even though the
  document's metadata and file bytes had already been saved successfully one line earlier.
  Fixed: `documents/upload_pipeline.py` now wraps the embed/upsert call the same way chat
  does — a vector-store failure leaves the document saved but not searchable via chat,
  logged and traced (`embed_failed` span attribute), instead of failing the whole upload.

## Never commit a real `REDIS_URL`

This connection string grants full read/write access to every estate in that database —
including uploaded documents' actual file bytes, which `set_document_file()` stores as
base64 blobs directly in Redis, not just metadata. A leaked credential means anyone can read
real users' actual uploaded documents (wills, bank statements, whatever they uploaded), not
just synthetic demo data. Keep it only in the local, gitignored `agent/.env` — never in
`.env.example` or anywhere else that gets committed.

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

Without `OPENAI_API_KEY` (or if the OpenAI call fails), `agent/llm/embeddings.py` falls back
to a deterministic hashing-trick bag-of-words vector — still exactly 1536 dimensions, so it
stays dimension-compatible with anything already written by real OpenAI embeddings. It's not
a real semantic embedding (no synonym/paraphrase understanding), but unlike hashing the whole
text as one blob, it hashes per-word, so texts sharing words score meaningfully more similar
than unrelated ones instead of the near-zero correlation a naive whole-string hash produces.

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

All three backends are implemented behind the stable store API. To stand up a real Redis
store, this is the checklist the implementation satisfies:

1. Pick one Redis provider: Redis Cloud (in use) or Upstash.
2. For Redis Cloud, confirm `VADD`, `VSIM`, and `VDIM` commands are available.
   For Upstash, create the Vector index using dimension `1536`.
3. Store `EstateState` as JSON at `estate:{estateId}`.
4. Validate every read back through Pydantic before returning it.
5. Vector upsert carries `estateId`, `source`, `documentType`, and `chunkIndex`
   metadata/attributes.
6. Semantic search cannot cross estates.
7. `/seed` is idempotent: it resets `demo-milligan` to the known demo state.
8. Integration coverage: seed, read estate, upsert chunks, search by estate ID.

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
