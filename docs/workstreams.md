# Workstreams

> **Status:** the build is essentially complete — all of the surfaces below are now
> implemented. This file is kept as the original parallel-development map showing where
> each member started and the stable boundaries they relied on.

Use this as the starting map for parallel development. The detailed task briefs still live
in `team/`; this file explains where each person began and which stable APIs they could
rely on.

## Member 1: Document Intelligence

Start in:

- `agent/llm/claude.py`
- `agent/llm/embeddings.py`
- `agent/documents/`
- `agent/prompts/extraction.py`

Stable dependencies available now:

- `agent/schemas/documents.py` has typed extraction models.
- `agent/store/redis_client.py` exposes `upsert_vectors()` and `merge_estate_state()`.
- `agent/agents/deadline_agent.py` exposes `run_deadline_agent()`.
- `POST /parse-document` exists in `agent/main.py`.

Replace the heuristic parsers and deterministic embeddings behind the existing function
signatures.

## Member 2: Data & Contracts

Start in:

- `agent/schemas/`
- `agent/store/redis_client.py`
- `agent/seed/demo_estate.py`
- `web/types/`
- `web/lib/schemas/`
- `docs/database.md`

Stable dependencies available now:

- Pydantic estate, alert, task, document, and auth models are importable.
- TypeScript interfaces and Zod schemas mirror the core shapes.
- KV is wired behind the store helpers, with vector search via Redis 8 Vector Sets
  (`STORE_BACKEND=redis_cloud`, in use) or Upstash Vector, and an in-memory fallback.
- `/seed` exists and is idempotent for `demo-milligan`.

Keep the seed/read and upsert/search integration checks in `docs/database.md` passing
against the configured backend.

## Member 3: DeadlineAgent + Reasoning

Start in:

- `agent/agents/deadline_agent.py`
- `agent/rules/california_probate.py`
- `agent/prompts/system.py`
- `agent/prompts/letters.py`
- `agent/observability/phoenix.py`

Stable dependencies available now:

- `get_estate_state()`, `get_alerts()`, and `write_alerts()` exist.
- `embed_query()` and `stream_chat()` exist as placeholders.
- `POST /deadline-agent`, `POST /chat`, and `POST /generate-letter` exist.
- The deterministic rule evaluator returns seed alerts for the dashboard.
- `agent/observability/phoenix.py` initializes Phoenix tracing on app startup and
  exposes `span()` for manual tracing.

Replace the deterministic agent with Claude tool-use while keeping the route contracts
stable for Member 4.

## Member 4: Frontend + Voice

Start in:

- `web/app/`
- `web/components/`
- `web/lib/agentClient.ts`
- `web/lib/deepgram.ts`
- `web/lib/sentry.ts`

Stable dependencies available now:

- The dashboard renders from `web/lib/mockEstate.ts` if the Python service is down.
- `web/app/api/agent/[...path]/route.ts` proxies all agent endpoints.
- `web/lib/agentClient.ts` exposes typed helpers for estate, alerts, document parse,
  chat streaming, and letters.
- `web/app/api/voice/*` exists with Deepgram stubs.

Build UI against the typed client first; swap stub voice/Sentry behavior behind
`web/lib/deepgram.ts` and `web/lib/sentry.ts`.
