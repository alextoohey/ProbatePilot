# Workstreams

Use this as the starting map for parallel development. The detailed task briefs still live
in `team/`; this file explains where each person should begin and which placeholder APIs
they can rely on.

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

- Pydantic estate, alert, task, document, and API models are importable.
- TypeScript interfaces and Zod schemas mirror the core shapes.
- Redis Cloud KV is wired behind the store helpers, and Redis 8 Vector Sets power
  semantic retrieval when `STORE_BACKEND=redis_cloud`.
- `/seed` exists and is idempotent for `demo-milligan`.

Before real demo usage, keep the seed/read and upsert/search integration checks in
`docs/database.md` passing against Redis Cloud.

## Member 3: DeadlineAgent + Reasoning

Start in:

- `agent/agents/deadline_agent.py`
- `agent/rules/california_probate.py`
- `agent/prompts/system.py`
- `agent/prompts/letters.py`
- `agent/observability/arize.py`

Stable dependencies available now:

- `get_estate_state()`, `get_alerts()`, and `write_alerts()` exist.
- `embed_query()` and `stream_chat()` exist as placeholders.
- `POST /deadline-agent`, `POST /chat`, and `POST /generate-letter` exist.
- The deterministic rule evaluator returns seed alerts for the dashboard.
- `agent/observability/arize.py` now initializes Arize AX tracing on app startup and
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
