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
├── researcher/             # Member 3: weekly probate-law ResearchAgent
├── documents/              # Member 1: document router and per-type parsers
├── llm/                    # Member 1: Claude client and embeddings helpers
├── auth/                   # bcrypt password hashing + cookie sessions
├── notify/                 # Resend weekly recap / alert digest
├── observability/          # Member 3: Phoenix OTLP + OpenInference span helpers
├── evals/                  # Member 3: LLM-as-judge DeadlineAgent eval
├── prompts/                # Members 1 and 3: extraction, chat, letter prompts
├── rules/                  # Member 3: California probate rule data/evaluators
├── schemas/                # Member 2: Pydantic contracts (estate, api, documents, auth)
├── seed/                   # Member 2: demo estate reset
├── tests/                  # pytest suite (rules, agents, chat, letters, …)
└── store/                  # Member 2: Redis boundary (memory / Redis Cloud / Upstash)
```

## Web App: `web/`

```
web/
├── app/                    # Member 4: Next.js pages and route handlers
├── components/             # Member 4: dashboard, chat, upload, voice UI
├── lib/                    # Member 4 + Member 2: agent client, Sentry, Zod schemas
└── types/                  # Member 2: TypeScript contracts mirroring Pydantic
```

## Graceful-Degradation Boundaries

The service is feature-complete, but every external dependency degrades gracefully so the
app still boots and demos without a full set of credentials:

- `agent/store/redis_client.py` runs in memory by default (`STORE_BACKEND=memory`) and
  switches to Redis Cloud (in use) or Upstash when credentials are present.
- `agent/llm/claude.py` and `agent/llm/embeddings.py` no-op into deterministic fallbacks
  when `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` are unset.
- `agent/documents/` falls back to heuristic extraction when Claude is unavailable.
- `agent/agents/deadline_agent.py` runs a Claude tool-use loop with a deterministic
  fallback so the dashboard always has alerts.
- `agent/notify/email.py` returns a preview instead of sending when `RESEND_API_KEY` is
  unset.
- `web/lib/mockEstate.ts` lets the dashboard render even if the Python service is down.
- `web/app/api/voice/*` returns previews until `DEEPGRAM_API_KEY` is set.

Keep these call signatures stable unless the owning members coordinate a contract update.
