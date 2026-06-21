# Executor AI

> The AI that prevents executors from making expensive mistakes — by building a live
> intelligence graph of the estate and running a true agent that alerts *before* probate
> deadlines and liability triggers are missed.

Built for the Hackathon @ Berkeley 2026 (24-hour build).

## What it does
Upload a will, deed, bank statement, or insurance policy. Claude parses each into a live
estate-state graph. An estate-aware chat (text + voice) answers questions grounded in
*your* documents. And a real agent — the **DeadlineAgent** — proactively reasons over
California probate law and tells you the next action before a missed deadline costs you.

## Architecture
Polyglot, two services + shared Redis. Python is the brain, TypeScript is the experience,
Redis is the memory.

```
web/  (Next.js + TypeScript)  ── HTTP / SSE ──▶  agent/  (FastAPI + Python)
  dashboard · chat UI · voice                     documents · RAG chat · DeadlineAgent
  Deepgram · Sentry                               Claude · embeddings · Arize AX
            └──────────────── Redis (KV state + vector search) ────────────────┘
```

## Stack
- **agent/** — Python · FastAPI · Anthropic (`claude-opus-4-8`, `claude-sonnet-4-6`) ·
  OpenAI embeddings · Pydantic · Arize AX tracing
- **web/** — Next.js 14 · TypeScript · Tailwind · Deepgram · Sentry · Zod
- **shared** — Redis Cloud: KV estate state + Redis 8 Vector Sets for document retrieval

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
Minimum to start: `ANTHROPIC_API_KEY` in `agent/.env`. Everything else runs on stubs.

## Team
| Member | Owns | Brief |
|--------|------|-------|
| 1 (Alex) | Document Intelligence (Python) | [member1](team/member1-document-intelligence.md) |
| 2 | Data & Contracts (Python + TS) | [member2](team/member2-data-layer.md) |
| 3 | DeadlineAgent + Reasoning (Python) | [member3](team/member3-deadline-agent.md) |
| 4 | Frontend + Voice (TS) | [member4](team/member4-frontend-chat-voice.md) |
