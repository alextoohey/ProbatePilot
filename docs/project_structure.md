# Project Structure

This repository is split by team ownership. Each member should work inside their owned
folder first, and only touch shared contracts after coordinating with the owner listed
below.

## Top-Level Layout

```
executor-ai/
├── agent/                  # Python FastAPI service: AI, RAG, documents, deadlines
├── web/                    # Next.js app: dashboard, chat, upload, voice
├── docs/                   # Shared implementation notes and ownership map
├── team/                   # Per-member task briefs
├── Makefile                # Dev commands: make install / make dev / make seed
├── README.md
├── CLAUDE.md
└── project_overview.md
```

## Python Service: `agent/`

```
agent/
├── main.py                 # FastAPI route wiring and stable API surface
├── agents/                 # Member 3: DeadlineAgent entrypoints
├── documents/              # Member 1: document router and per-type parsers
├── llm/                    # Member 1: Claude client and embeddings helpers
├── observability/          # Member 3: Arize AX span helpers + Phoenix shim
├── prompts/                # Members 1 and 3: extraction, chat, letter prompts
├── rules/                  # Member 3: California probate rule data/evaluators
├── schemas/                # Member 2: Pydantic contracts
├── seed/                   # Member 2: demo estate reset
└── store/                  # Member 2: Redis boundary and in-memory fallback
```

## Web App: `web/`

```
web/
├── app/                    # Member 4: Next.js pages and route handlers
├── components/             # Member 4: dashboard, chat, upload, voice UI
├── lib/                    # Member 4 + Member 2: agent client, Sentry, Zod schemas
└── types/                  # Member 2: TypeScript contracts mirroring Pydantic
```

## Placeholder Boundaries

The scaffold intentionally includes working placeholders so team members can build in
parallel:

- `agent/store/redis_client.py` can run in memory for offline work or use Redis Cloud for
  KV plus Redis 8 Vector Sets for document retrieval.
- `docs/database.md` defines the Redis KV/vector contract and the replacement checklist.
- `docs/workstreams.md` gives each member a start-here map and stable dependencies.
- `agent/llm/claude.py` and `agent/llm/embeddings.py` expose stable helper functions
  without requiring API keys.
- `agent/documents/` returns typed heuristic extractions so upload and merge flows can be
  built before Claude parsing is finished.
- `agent/agents/deadline_agent.py` returns deterministic alerts from the seed estate so
  the dashboard can render the core demo immediately.
- `web/lib/mockEstate.ts` lets the dashboard render even if the Python service is down.
- `web/app/api/voice/*` returns stub responses until Deepgram is wired.

Replace placeholders behind these boundaries without changing call signatures unless the
owning members coordinate a contract update.
