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

## How To Approach It

### Step 1 — The contract (do this first)
Define every shape once, conceptually, then express it twice:
- **Pydantic v2** in `agent/schemas/` — the source of truth. Python validates Claude
  output and Redis reads/writes against these.
- **TS types + Zod** in `web/` — mirror the Pydantic models field-for-field.

Use **camelCase field names on the wire** so both sides agree without translation. The
shapes are specified in
[project_overview.md §5](../project_overview.md#5-core-data-shapes) — EstateState and its
parts, Alert, and the per-document extractions. Agree the extraction fields with Member 1.

Keep types and validators cleanly separated within each language (models vs. schemas).

### Step 2 — Redis client (`agent/store/redis_client.py`)
This is the *only* place Redis is touched. Expose a small, well-named surface:
- KV: get / set / merge estate state under `estate:{id}`; update `updatedAt` on write.
- Vector: upsert chunks+embeddings (store the chunk text and `estateId` in metadata);
  semantic search that **filters by `estateId`** and returns chunk text (and score/source
  so Member 4 can show citations).
- Alerts: read / write the alert list for an estate.
- A `merge_estate_state` that deep-merges a partial update into the current state and
  creates a blank estate if none exists (Member 1 calls this from the parse pipeline).

Use Redis Cloud for the hackathon sponsor story. The current implementation stores estate
KV under `estate:{id}` and uses Redis 8 Vector Sets under `estate:{id}:chunks`, with
`text-embedding-3-small` vectors at 1536 dimensions. Keep the provider details behind
this module so a later switch is a one-file change.

### Step 3 — Seed data (`agent/seed/demo_estate.py`)
The demo estate (`demo-milligan`,
[project_overview.md §9](../project_overview.md#9-demo-scenario)) must be loadable at any
moment to reset the demo to a known-good state. Expose a `POST /seed` route that writes it
and returns cleanly. This is your single most-used artifact during rehearsal — make it
reliable.

---

## Contracts & Coordination
| You need from… | What |
|----------------|------|
| **Member 1** | Agreement on the per-document extraction field shapes |
| Nobody else — you build first | Models + Redis helpers must be ready in hour ~2 |

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
- **Anthropic / Arize** — airtight Pydantic validation means Claude outputs are typed and
  trustworthy before they ever reach Redis; bad outputs fail loudly and show up in traces.
