# Member 2 — Data & Contracts (Python + TS)

**Owner**: Davyn
**Languages**: Python (`agent/schemas/`, `agent/store/`, `agent/seed/`) **and**
TypeScript (`web/types/`, `web/lib/schemas/`)
**Track dependency**: You are the shared foundation. The estate-state contract and the
Redis helpers must exist in the first couple of hours so everyone else can build on them.

---

## Your Mission
You own all data infrastructure and the **contract** between the two services: the
Pydantic models that the Python brain validates against, the matching TypeScript types +
Zod schemas the web layer uses, the Redis client (KV + vector), and the demo seed data.
Every other member reads or writes the estate state you define. Build the contract first,
then the Redis helpers that move it around.

You are the only person working in both languages — that is deliberate. Keeping the two
representations of the same shapes in sync is your job.

---

## What You Own
```
agent/
├── schemas/            # Pydantic v2 models: EstateState, Asset, Debt, Beneficiary,
│                       #   Task, UploadedDocument, Alert, and per-doc extractions
├── store/
│   └── redis_client.py # Redis KV + vector helpers (the only Redis access point)
└── seed/
    └── demo_estate.py  # DEMO_ESTATE object + reset routine + POST /seed handler

web/
├── types/              # TS interfaces mirroring the Pydantic models
└── lib/schemas/        # Zod schemas for anything crossing the wire into the browser
```

---

## What's Already Done

The scaffold has working stubs for everything you own — your job is to **refine and
replace**, not start from scratch:

- `agent/schemas/estate.py` — full Pydantic models for `EstateState`, `Asset`, `Debt`,
  `Beneficiary`, `Task`, `Alert`, `UploadedDocument`. Already importable, no errors.
- `agent/schemas/documents.py` — `WillExtraction`, `BankStatementExtraction`,
  `DeedExtraction` with all fields defined. Agree any additions with Member 1.
- `agent/schemas/api.py` — request/response models for every route.
- `agent/store/redis_client.py` — **in-memory implementation** with the full stable API
  already wired (`get_estate_state`, `set_estate_state`, `merge_estate_state`,
  `upsert_vectors`, `semantic_search`, `write_alerts`, `get_alerts`, `add_document`,
  `seed_demo_estate`). Every other member already calls these.
- `agent/seed/demo_estate.py` — `DEMO_ESTATE` object complete. `POST /seed` exists in
  `main.py` and works today.
- `web/types/` and `web/lib/schemas/` — TS types and Zod schemas mirroring the Pydantic
  models.

---

## How To Approach It

### Step 1 — Verify and extend the schemas
Read through `agent/schemas/` and `web/types/`. The core shapes are done; your job is:
- Confirm extraction fields with Member 1 (`agent/schemas/documents.py`) — add any fields
  their parsers need that aren't there yet.
- Keep TS types in `web/types/` in sync with any Pydantic changes — camelCase on the wire,
  same field names on both sides.
- Keep types and validators cleanly separated within each language (models vs. schemas).

### Step 2 — Replace the in-memory store with real Redis
`agent/store/redis_client.py` currently stores everything in Python dicts (`_ESTATES`,
`_VECTORS`). **All function signatures must stay identical** — other members already import
and call them. Only the implementation changes.

The env var `STORE_BACKEND` in `agent/.env` is already wired as a toggle:
- `STORE_BACKEND=memory` — current default, works with no credentials
- `STORE_BACKEND=upstash` — switch to real Redis once credentials are ready

Pick one provider:
- **Upstash** (recommended) — serverless, REST-based, no connection management. Use
  `upstash-redis` for KV and `upstash-vector` for the vector index.
- **Redis Cloud** — sponsor credits available; use the `redis` Python client.

Use Redis Cloud for the hackathon sponsor story. The current implementation stores estate
KV under `estate:{id}` and uses Redis 8 Vector Sets under `estate:{id}:chunks`, with
`text-embedding-3-small` vectors at 1536 dimensions. Keep the provider details behind
this module so a later switch is a one-file change.

Real Redis implementation checklist (from `docs/database.md`):
1. Create the `estate_chunks` vector index with the correct embedding dimension (1536 for
   `text-embedding-3-small`).
2. Store `EstateState` as JSON at `estate:{estateId}` — validate reads through Pydantic.
3. Upsert vectors with `estateId`, `source`, `documentType`, `chunkIndex` metadata.
4. Semantic search must filter by `estateId` — cross-estate retrieval is a correctness bug.
5. Return score + source in search results so Member 4 can show citations in chat.
6. Keep `POST /seed` idempotent — it must reset `demo-milligan` reliably at any point.

### Step 3 — Integration check before the demo
One end-to-end test: `make seed` → read estate back → upsert a test chunk → search by
`estateId` → confirm the right chunk comes back. This is the sanity check that real Redis
is wired correctly before everyone depends on it.

---

## Contracts & Coordination
| You need from… | What |
|----------------|------|
| **Member 1** | Confirm any extraction fields they need added to `agent/schemas/documents.py` |
| **Redis credentials** | Upstash or Redis Cloud credentials before you can replace the in-memory store |

| Others need from you | What |
|----------------------|------|
| **Member 1** | Extraction Pydantic models; `upsert_vectors`, `merge_estate_state` |
| **Member 3** | `get_estate_state`, `write_alerts`, `get_alerts`; EstateState + Alert models |
| **Member 4** | TS types + Zod for the dashboard/chat; (search results flow through Member 3's endpoints, but the *shapes* are yours) |
| **Everyone** | One source of truth for every estate shape, in both languages |

---

## Acceptance Criteria
- [ ] Pydantic models for EstateState (+ parts), Alert, and every extraction — importable,
      no errors.
- [ ] TS types + Zod schemas mirror the Pydantic models field-for-field (camelCase).
- [ ] `redis_client.py` exposes get/set/merge estate, upsert/search vectors (filtered by
      `estateId`), and read/write alerts.
- [ ] `POST /seed` writes DEMO_ESTATE and round-trips (write → read back) without error.
- [ ] Both KV and Redis Vector Sets connect and are verified by a seed-then-read +
      upsert-then-search check.

---

## Sponsor Hooks You Unlock
- **Redis** — your module *is* the Redis story: vector search as agent memory + retrieval,
  scoped per `estateId`, not caching. Make search return text **and** metadata
  (score/source) so the chat can cite documents.
- **Anthropic / Phoenix** — airtight Pydantic validation means Claude outputs are typed and
  trustworthy before they ever reach Redis; bad outputs fail loudly and show up in traces.
