# OpenWolf

@.wolf/OPENWOLF.md

This project uses OpenWolf for context management. Read and follow .wolf/OPENWOLF.md every session. Check .wolf/cerebrum.md before generating code. Check .wolf/anatomy.md before reading files.


# Executor AI — Claude Instructions

## What This Is
An AI executor assistant. It parses estate documents into a live state graph, then
proactively alerts the executor *before* probate deadlines and liability triggers are
missed. The differentiator is a real **agent** — the DeadlineAgent — that reasons over
estate state against California probate law and surfaces the next action before the
executor knows to ask. Built with Claude for a 24-hour hackathon.

Full project detail: [project_overview.md](project_overview.md)
Tracks & sponsors: [hackathon_tracks_and_prizes.md](hackathon_tracks_and_prizes.md)

---

## Architecture at a Glance
This is a **polyglot** project — two services sharing one Redis state store. Use each
language for what it is best at; do not collapse everything into one stack.

```
┌────────────────────────┐         ┌─────────────────────────────┐
│  web/  (TypeScript)     │  HTTP   │  agent/  (Python)            │
│  Next.js 14 frontend    │ ──────▶ │  FastAPI "brain"             │
│  • Dashboard / chat UI  │  SSE    │  • Document intelligence     │
│  • Deepgram voice       │ ◀────── │  • RAG chat (streaming)      │
│  • Sentry observability │         │  • DeadlineAgent (tool-use)  │
└───────────┬─────────────┘         │  • Letter generation         │
            │                       │  • Phoenix tracing          │
            │                       └──────────────┬──────────────┘
            │        Redis (KV estate state + vector search)        │
            └───────────────────────┬──────────────────────────────┘
                                    ▼
                          Redis Cloud
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
  - `claude-opus-4-8` — DeadlineAgent reasoning + RAG chat (the hard reasoning)
  - `claude-sonnet-4-6` — document parsing (vision + structured) + letter drafting
- **Embeddings**: OpenAI `text-embedding-3-small` (`openai`)
- **Validation**: Pydantic v2 for all Claude structured outputs and API schemas
- **Observability**: Phoenix tracing (`phoenix.otel.register` + OpenInference) — traces
  Anthropic, OpenAI embeddings, and the full agent loop
- **Dates**: `python-dateutil` / stdlib `datetime` for all deadline arithmetic
- **Documents**: `pypdf` / `pdfplumber` for text, Claude vision for scans/images

### `web/` — Next.js frontend (the experience)
- **Framework**: Next.js 14 App Router, TypeScript, Tailwind CSS
- **AI (client of the agent)**: calls `agent/` over HTTP; streams chat via SSE
- **Voice**: Deepgram STT + TTS (`@deepgram/sdk`)
- **Observability**: Sentry (`@sentry/nextjs`)
- **Validation**: Zod — mirrors the Pydantic contract for anything crossing the wire

### Shared
- **State + vectors**: Redis Cloud. KV holds estate state; Redis 8 Vector Sets power RAG /
  agent memory with 1536-dimensional `text-embedding-3-small` vectors.

---

## Key File Locations

### Python (`agent/`)
| Purpose | Path |
|---------|------|
| FastAPI app entrypoint | `agent/main.py` |
| Anthropic client + helpers | `agent/llm/claude.py` |
| OpenAI embeddings | `agent/llm/embeddings.py` |
| Redis client (KV + vector) | `agent/store/redis_client.py` |
| Pydantic models | `agent/schemas/` |
| Document parsers | `agent/documents/` |
| DeadlineAgent (tool-use loop) | `agent/agents/deadline_agent.py` |
| CA probate rules | `agent/rules/california_probate.py` |
| Prompts | `agent/prompts/` |
| Phoenix setup | `agent/observability/phoenix.py` |
| Demo seed data | `agent/seed/demo_estate.py` |

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
| Route | Method | Purpose |
|-------|--------|---------|
| `/parse-document` | POST | File upload → Claude extract → embed → Redis |
| `/chat` | POST | Message → RAG retrieve → Claude stream (SSE) |
| `/deadline-agent` | POST | Run the agent loop → return ranked alerts |
| `/generate-letter` | POST | Letter type + estate → Claude draft |
| `/seed` | POST | Reset demo estate to a known-good state |

### TypeScript `web/` (Next.js route handlers)
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/voice/transcribe` | POST | Audio → Deepgram STT → text |
| `/api/voice/speak` | POST | Text → Deepgram TTS → audio |
| `/api/agent/*` | * | Thin Sentry-wrapped proxy to the Python service |

---

## Core Data Shapes (the contract)
These shapes are defined once as **Pydantic models** in `agent/schemas/` and mirrored as
**TypeScript types + Zod schemas** in `web/`. Member 2 owns keeping the two in sync.

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

Full field-level definitions live in [project_overview.md](project_overview.md#core-data-shapes).

---

## Environment Variables

```bash
# agent/.env  (Python service — never commit)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
UPSTASH_VECTOR_REST_URL=
UPSTASH_VECTOR_REST_TOKEN=
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=executor-ai-agent
PHOENIX_API_KEY=

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
Appointment: 2026-06-10 | Executor: Dana Milligan.

Designed to fire live during the demo:
1. **CRITICAL** — DE-160 Inventory & Appraisal due ~9 days out, no appraisal uploaded.
2. **CRITICAL** — Creditors not notified; 30-day window from June 10 nearly elapsed.

Full seed object: [project_overview.md](project_overview.md#demo-scenario).

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
  personal liability. The DeadlineAgent must flag this.
- Never give legal advice in chat. Use: *"This requires your attorney's input — it
  involves [reason]."*
- Tone: warm and direct. Never clinical. This person is grieving.

---

## Team Division
- **Member 1 (Alex)** — Document Intelligence (Python): Claude parsers, embeddings,
  parse pipeline → [team/member1-document-intelligence.md](team/member1-document-intelligence.md)
- **Member 2** — Data & Contracts (Python + TS): Redis, Pydantic/Zod/TS schemas, estate
  state, seed data → [team/member2-data-layer.md](team/member2-data-layer.md)
- **Member 3** — DeadlineAgent + Reasoning (Python): agent loop, rules engine, chat RAG,
  letters, Phoenix → [team/member3-deadline-agent.md](team/member3-deadline-agent.md)
- **Member 4** — Frontend + Voice (TS): all UI, Deepgram, Sentry, BFF proxy
  → [team/member4-frontend-chat-voice.md](team/member4-frontend-chat-voice.md)
