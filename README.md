# ProbatePilot

> The AI that prevents executors from making expensive mistakes — by building a live
> intelligence graph of the estate and running a true agent that alerts *before* probate
> deadlines and liability triggers are missed.

Built for the Hackathon @ Berkeley 2026 (24-hour build).

## The problem
When someone dies, the **executor** — usually a grieving family member, not a lawyer — is
personally responsible for administering the estate: probate filings, asset inventory,
creditor notices, debts paid in the right legal order, taxes, and distributions. Miss a
deadline or pay out of order and the executor can be held *personally* liable. Families who
can't afford a probate attorney do this alone, spending ~180 hours and making expensive
mistakes nobody warned them about.

ProbatePilot is the expert in their corner: it reconstructs the estate from its documents
and tells the executor the next action *before* it costs them. California probate only, and
never a substitute for legal advice — for attorney-judgment questions it says so plainly.

## What it does
Sign in, create an estate, and upload a will, deed, bank statement, or creditor notice.
Claude parses each into a live estate-state graph. An estate-aware chat (text + voice)
answers questions grounded in *your* documents. A real agent — the **DeadlineAgent** —
proactively reasons over California probate law and tells you the next action before a
missed deadline costs you, and a second **ResearchAgent** watches weekly for probate-law
changes. Generated letters and emailed alert digests close the loop.

## Architecture
Polyglot, two services + shared Redis. Python is the brain, TypeScript is the experience,
Redis is the memory.

```
web/  (Next.js + TypeScript)  ── HTTP / SSE ──▶  agent/  (FastAPI + Python)
  auth · dashboard · chat · voice                 auth · documents · RAG chat
  Deepgram · Sentry                               DeadlineAgent · ResearchAgent
                                                  letters · email · Phoenix + evals
            └──────────────── Redis (KV state + vector search) ────────────────┘
```

## Stack
- **agent/** — Python · FastAPI · Anthropic (`claude-sonnet-4-6` across parsing, the
  agents, chat, and letters) · OpenAI embeddings · Pydantic · bcrypt auth · Resend email
  · Phoenix tracing + LLM-as-judge evals
- **web/** — Next.js 14 · TypeScript · Tailwind · Deepgram · Sentry · Zod
- **shared** — Redis: KV estate state + vector search for document retrieval, behind a
  store layer that supports Redis Cloud (cloud path in use), Upstash, or in-memory backends

## Repo layout
- [`CLAUDE.md`](CLAUDE.md) — working instructions for Claude / coding agents
- [`project_overview.md`](project_overview.md) — full design, data shapes, flows, demo
- [`hackathon_tracks_and_prizes.md`](hackathon_tracks_and_prizes.md) — tracks & sponsors
- [`docs/project_structure.md`](docs/project_structure.md) — implementation folders,
  ownership boundaries, and placeholder contracts
- [`docs/database.md`](docs/database.md) — Redis KV/vector contract and database setup
  checklist
- [`docs/workstreams.md`](docs/workstreams.md) — per-member start points and stable
  dependency boundaries
- [`team/`](team/) — per-member role briefs (Members 1–4)
- `agent/` — Python service · `web/` — Next.js frontend

## Getting started
```bash
# 1. Copy env files (won't overwrite if they already exist)
make env

# 2. Install all dependencies (uv for Python, npm for web)
make install

# 3. Start both services — agent on :8000, web on :3000
make dev

# 4. In a separate terminal: seed the demo estate
make seed
```

Fill in your API keys in `agent/.env` and `web/.env.local` after running `make env`.
Minimum to start: `ANTHROPIC_API_KEY` in `agent/.env`. The store defaults to
`STORE_BACKEND=memory`, so Redis Cloud is optional for local dev; voice (Deepgram),
email (Resend), and observability (Phoenix/Sentry) degrade gracefully when their keys are
unset — voice and email return previews instead of failing.

Phoenix tracing sends Anthropic, OpenAI embedding, and custom agent spans to
`PHOENIX_COLLECTOR_ENDPOINT` (defaults to `http://localhost:6006/v1/traces`). Set
`PHOENIX_API_KEY` when using Phoenix Cloud; local Phoenix does not require one.

## Team
| Member | Owns | Brief |
|--------|------|-------|
| 1 (Alex) | Document Intelligence (Python) | [member1](team/member1-document-intelligence.md) |
| 2 | Data & Contracts (Python + TS) | [member2](team/member2-data-layer.md) |
| 3 | DeadlineAgent + Reasoning (Python) | [member3](team/member3-deadline-agent.md) |
| 4 | Frontend + Voice (TS) | [member4](team/member4-frontend-chat-voice.md) |
