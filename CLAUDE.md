# ProbatePilot — Claude Instructions

## What This Is
An AI copilot for estate executors. It parses estate documents into a live state graph,
then proactively alerts the executor *before* probate deadlines and liability triggers are
missed. The differentiator is a real **agent** — the DeadlineAgent — that reasons over
estate state against California probate law and surfaces the next action before the
executor knows to ask. Originally built at UC Berkeley AI Hackathon 2026 in 24 hours.

Full project detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Architecture at a Glance
This is a **polyglot** project — two services sharing one Redis state store. Use each
language for what it is best at; do not collapse everything into one stack.

```
┌────────────────────────┐         ┌─────────────────────────────┐
│  web/  (TypeScript)     │  HTTP   │  agent/  (Python)            │
│  Next.js 14 frontend    │ ──────▶ │  FastAPI "brain"             │
│  • Dashboard / chat UI  │  SSE    │  • Auth (login / register)   │
│  • Deepgram voice       │ ◀────── │  • Document intelligence     │
│  • Sentry observability │         │  • RAG chat (streaming)      │
└───────────┬─────────────┘         │  • DeadlineAgent (tool-use)  │
            │                       │  • ResearchAgent (law watch) │
            │                       │  • Letter gen · Email (Resend)│
            │                       │  • Phoenix tracing + evals   │
            │                       └──────────────┬──────────────┘
            │        Redis (KV estate state + vector search)        │
            └───────────────────────┬──────────────────────────────┘
                                    ▼
              Redis Cloud (KV + Redis 8 Vector Sets)
               (Upstash / in-memory backends also supported)
```

- **Python (`agent/`)** owns all Claude reasoning, document parsing, embeddings, the
  agent loop, and RAG. This is the "hard AI" surface and the Anthropic-prize story.
- **TypeScript (`web/`)** owns everything the judge sees and touches, plus voice.
- **Redis** is the only thing both services talk to. It is the contract.

---

## Stack (Quick Reference)

### `agent/` — Python service (the brain)
- **Framework**: FastAPI + Uvicorn, Python 3.11+
- **AI**: Anthropic Python SDK (`anthropic`)
  - `claude-sonnet-4-6` — the model used across the whole service today: document
    parsing (vision + structured), DeadlineAgent reasoning, RAG chat, and letters.
    `agent/llm/claude.py` exposes `DOCUMENT_MODEL` and `REASONING_MODEL` (both
    `claude-sonnet-4-6`) — swap `REASONING_MODEL` to `claude-opus-4-8` if you want the
    heavier reasoning path back.
- **Embeddings**: OpenAI `text-embedding-3-small` (`openai`), 1536-dim
- **Auth**: cookie sessions with `bcrypt` password hashing (`agent/auth/`)
- **Email**: Resend for the weekly recap / alert digest (`agent/notify/email.py`)
- **Validation**: Pydantic v2 for all Claude structured outputs and API schemas
- **Observability**: Phoenix tracing (`phoenix.otel.register` + OpenInference) — traces
  Anthropic, OpenAI embeddings, and the full agent loop; plus an LLM-as-judge eval
  (`agent/evals/deadline_next_steps_quality.py`)
- **Dates**: `python-dateutil` / stdlib `datetime` for all deadline arithmetic
- **Documents**: `pdfplumber` for text, Claude vision for scans/images and scanned PDFs;
  `pillow` + `pillow-heif` for image/HEIC handling

### `web/` — Next.js frontend (the experience)
- **Framework**: Next.js 14 App Router, TypeScript, Tailwind CSS
- **AI (client of the agent)**: calls `agent/` over HTTP; streams chat via SSE
- **Voice**: Deepgram STT + TTS (`@deepgram/sdk`)
- **Observability**: Sentry (`@sentry/nextjs`)
- **Validation**: Zod — mirrors the Pydantic contract for anything crossing the wire

### Shared
- **State + vectors**: KV holds estate state; a vector store powers RAG / agent memory
  with 1536-dimensional `text-embedding-3-small` vectors. `agent/store/` supports three
  interchangeable backends behind one API, selected by `STORE_BACKEND`: `redis_cloud`
  (Redis Cloud KV + Redis 8 Vector Sets — the cloud path this project runs on), `upstash`
  (Upstash Redis REST + Upstash Vector — also supported), and `memory` (in-process
  fallback for offline dev). `make`/`.env.example` default to `memory`.

---

## Key File Locations

### Python (`agent/`)
| Purpose | Path |
|---------|------|
| FastAPI app factory (routers only — no route logic) | `agent/main.py` |
| Auth + estate-ownership dependencies | `agent/api/deps.py` |
| Route handlers, one file per domain | `agent/api/routers/` |
| Anthropic client + helpers | `agent/llm/claude.py` |
| OpenAI embeddings | `agent/llm/embeddings.py` |
| Store domain layer (key naming, validation) | `agent/store/redis_client.py` |
| Store backends (memory / Upstash / Redis Cloud) | `agent/store/backends/` |
| Pydantic models | `agent/schemas/` (estate, api, documents, auth) |
| Document parsers (will/bank/deed/creditor) | `agent/documents/` |
| Upload → extract → merge → embed pipeline | `agent/documents/upload_pipeline.py` |
| DeadlineAgent (tool-use loop) | `agent/agents/deadline_agent.py` |
| ResearchAgent (weekly probate-law watch) | `agent/researcher/research_agent.py` |
| CA probate rules | `agent/rules/california_probate.py` |
| Auth (bcrypt + sessions) | `agent/auth/security.py` |
| Email notifications (Resend) | `agent/notify/email.py` |
| LLM-as-judge eval | `agent/evals/deadline_next_steps_quality.py` |
| Prompts | `agent/prompts/` |
| Phoenix setup | `agent/observability/phoenix.py` |
| Demo seed data | `agent/seed/demo_estate.py` |
| Shared constants (e.g. `DEFAULT_ESTATE_ID`) | `agent/constants.py` |

### TypeScript (`web/`)
| Purpose | Path |
|---------|------|
| Deepgram client | `web/lib/deepgram.ts` |
| Agent API client (typed fetch wrapper) | `web/lib/agentClient.ts` |
| Sentry wrappers | `web/lib/sentry.ts` |
| Shared TS types (mirror Pydantic) | `web/types/` |
| Zod schemas | `web/lib/schemas/` |
| API routes (proxy + voice) | `web/app/api/` |
| UI components | `web/components/` |

---

## API Surface

### Python `agent/` (FastAPI)
Every route below except `/health`, `/seed`, and `/auth/*` requires a session and estate
ownership (`api/deps.py::ensure_estate_access`) — the one exception is the seeded demo
estate (`demo-milligan`), which stays world-readable so the demo works without signing up.

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Service status + Phoenix/instrumentor readiness |
| `/auth/register` · `/auth/login` · `/auth/logout` | POST | Account + cookie session |
| `/auth/demo` | POST | Guest session scoped to the seeded demo estate, no registration |
| `/auth/me` | GET | Current authenticated user |
| `/estates` | POST | Create a real estate shell |
| `/estate/{estate_id}` | GET | Fetch full estate state |
| `/seed` | POST | Reset demo estate to a known-good state |
| `/parse-document` · `/parse-documents` | POST | Upload(s) → Claude extract → embed → store |
| `/document/{estate_id}/{doc_id}` | GET / DELETE | Fetch or remove an uploaded document |
| `/deadline-agent` | POST | Run the agent loop → return ranked alerts |
| `/research-agent` | POST | Weekly probate-law watch → review alerts |
| `/complete-alert` | POST | Mark an alert/step done → updated estate |
| `/chat` | POST | Message → RAG retrieve → Claude stream (SSE) |
| `/chat-history/{estate_id}` · `/chat-sessions/{estate_id}` | GET / POST | Chat persistence |
| `/chat-suggestions` | POST | Suggested follow-up questions |
| `/generate-letter` · `/save-letter` | POST | Draft / persist a letter |
| `/letter/{estate_id}/{letter_id}` | DELETE | Remove a saved letter |
| `/notify/email` | POST | Send weekly recap / alert digest via Resend |

### TypeScript `web/` (Next.js route handlers)
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/auth/{login,logout,register,me}` | * | Auth proxied to the Python service |
| `/api/voice/transcribe` | POST | Audio → Deepgram STT → text |
| `/api/voice/speak` | POST | Text → Deepgram TTS → audio |
| `/api/agent/*` | * | Thin Sentry-wrapped proxy to the Python service |

---

## Core Data Shapes (the contract)
These shapes are defined once as **Pydantic models** in `agent/schemas/` and mirrored as
**TypeScript types + Zod schemas** in `web/`. Keep the two in sync when either changes.

```
EstateState (Redis KV key: estate:{id})
  id, deceasedName, dateOfDeath (ISO), appointmentDate (ISO),
  state="california", executor{name,email},
  assets[], debts[], beneficiaries[], documents[], tasks[], alerts[],
  phase: 1..6, createdAt, updatedAt

Alert (output of DeadlineAgent)
  id, severity: critical|warning|info,
  type: deadline|liability|missing_doc|rule_violation,
  title, body, rule, daysRemaining?, actionRequired, createdAt, dismissed
```

Full field-level definitions live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#core-data-shapes).

---

## Environment Variables

See `agent/.env.example` and `web/.env.local.example` for the complete, authoritative
lists. Key variables:

```bash
# agent/.env  (Python service — never commit)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
STORE_BACKEND=memory            # memory | upstash | redis_cloud
REDIS_URL=                      # redis_cloud backend (use rediss:// for TLS)
UPSTASH_REDIS_REST_URL=         # upstash backend
UPSTASH_REDIS_REST_TOKEN=
UPSTASH_VECTOR_REST_URL=
UPSTASH_VECTOR_REST_TOKEN=
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=probatepilot-agent
PHOENIX_API_KEY=
PHOENIX_EVAL_PROVIDER=anthropic         # DeadlineAgent eval judge
PHOENIX_EVAL_MODEL=claude-sonnet-4-6
PHOENIX_CAPTURE_EVAL_CONTEXT=false       # opt-in; captures estate facts in spans
RESEND_API_KEY=                 # email notifications (preview-only if unset)
EMAIL_FROM=onboarding@resend.dev
NOTIFY_OVERRIDE_RECIPIENT=      # force all mail to one address (demo/testing)

# web/.env.local  (Next.js — never commit)
AGENT_API_URL=http://localhost:8000
DEEPGRAM_API_KEY=
NEXT_PUBLIC_SENTRY_DSN=
SENTRY_DSN=
SENTRY_ORG=
SENTRY_PROJECT=
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## Demo Estate (Seed Data)
Estate ID `demo-milligan` | Deceased: Robert A. Milligan | Date of death: 2026-06-03 |
Appointment: 2026-06-10 | Executor: Dana Milligan. The canonical object lives in
`agent/seed/demo_estate.py` (`build_demo_estate()`); `POST /seed` resets it.

Designed to fire live during the demo (exact day counts depend on the run date):
1. **CRITICAL** — Creditors not yet notified; the 30-day certified-mail window from the
   June 10 appointment is closing.
2. **CRITICAL** — DE-160 Inventory & Appraisal outstanding with no property appraisal on
   the Berkeley home or the Honda Civic.

Full seed object: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#demo-scenario).

---

## Critical Rules
- **Never commit `agent/.env` or `web/.env.local`.**
- Every Claude and OpenAI embedding call is traced. In Python that means it runs inside a Phoenix
  span tagged with `estate_id` and `action_type`. In the web layer, wrap the proxy call
  in a Sentry span.
- Validate **every** Claude structured output (Pydantic in `agent/`) before writing to
  Redis. Anything crossing to the browser is re-validated with Zod.
- CA probate jurisdiction only — hardcoded for the hackathon.
- Debt payment order: secured → unsecured → distributions. Out-of-order = executor
  personal liability. `rules/california_probate.py`'s `debt-order` rule flags this the
  moment an unsecured/priority creditor is notified before a secured one is.
- Never give legal advice in chat. Use: *"This requires your attorney's input — it
  involves [reason]."*
- Tone: warm and direct. Never clinical. This person is grieving.

---

## Origin
Built by a 4-person team at UC Berkeley AI Hackathon 2026 in 24 hours. See the README
for full credits.
