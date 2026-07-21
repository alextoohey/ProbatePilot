# ProbatePilot

**An AI copilot that keeps estate executors ahead of every probate deadline.**

Built in 24 hours at UC Berkeley AI Hackathon 2026 by a 4-person team, for the
technology-and-social-impact track.

![ProbatePilot dashboard — critical alerts on the seeded demo estate](docs/assets/dashboard.png)

[Run it locally in 3 commands](#quick-start) — see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
to put up a live version.

---

## The problem

When someone dies, the **executor** — usually a grieving family member, not a lawyer — is
personally on the hook for administering the estate: probate filings, an asset inventory,
creditor notices, debts paid in a specific legal order, taxes, distributions. Miss a
deadline, or pay creditors out of order, and the executor can be held *personally* liable
for the mistake. Most families can't afford a probate attorney for every question, so they
do this alone — typically over 100+ hours, with no one telling them what's coming next.

ProbatePilot reads the estate's documents, builds a live picture of what's known and what's
missing, and tells the executor the next action *before* it becomes expensive. It's scoped
to California probate law for now, and it knows what it doesn't know: for anything requiring
legal judgment, it says so plainly instead of guessing.

## What it does

- **Upload a document, get a structured estate.** A will, a deed, a bank statement, a
  creditor notice — Claude reads it and extracts the assets, debts, beneficiaries, and dates
  into one running estate record.
- **The DeadlineAgent watches the clock.** A deterministic California probate rule engine
  evaluates the estate against real statutory deadlines (DE-160 inventory, the 30-day
  creditor-notice window, debt payment order, and more); Claude then reasons over the result
  to rank and explain it in plain language. The rules always win — Claude can rewrite the
  copy, never the facts.
- **Ask it anything.** An estate-aware chat (text or voice) answers questions grounded in
  the executor's own uploaded documents, not generic advice.
- **It writes the letters.** Creditor notices, bank notifications, beneficiary updates —
  drafted from the estate's actual facts, ready to sign.

<p float="left">
  <img src="docs/assets/documents.png" width="49%" alt="Document upload with the parsing checklist" />
  <img src="docs/assets/chat.png" width="49%" alt="Estate-aware chat grounded in the uploaded documents" />
</p>

## How it works

```
┌──────────────────────┐   HTTP / SSE   ┌───────────────────────────┐
│  web/ (Next.js 14)    │───────────────▶│  agent/ (FastAPI)         │
│  dashboard · chat     │◀───────────────│  DeadlineAgent · RAG chat │
│  voice (Deepgram)     │                │  document intelligence   │
│  Sentry                │                │  Phoenix tracing + evals │
└───────────┬───────────┘                └─────────────┬─────────────┘
            │                                            │
            └──────────────── Redis (estate KV + vector search) ─────┘
```

Two services, one shared store, each language doing what it's good at: Python owns Claude
reasoning and document parsing, TypeScript owns everything the user touches. The browser
never talks to the Python service directly — every call is proxied through Next.js, which
forwards the session as a bearer token server-side, so there's no CORS surface to manage.

**A few things worth a closer look if you're reading the code:**

- **The DeadlineAgent is deterministic-first.** `evaluate_rules()` runs a pure-function rule
  table against estate state and always produces a complete, correct alert set — with zero
  LLM involvement. Claude then gets a bounded tool-use loop to improve the wording, but its
  output is validated against the deterministic alerts and rejected if it drops or invents
  one. A missing API key or a bad model response both degrade to the same rule-evaluated
  alerts, just plainer prose. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- **The store is a real backend abstraction, not a wrapper around one database.**
  `agent/store/` supports three interchangeable backends — in-memory (default, zero setup),
  Upstash Redis, and Redis Cloud with Redis 8 Vector Sets for semantic search — behind one
  API, selected by an env var.
- **Auth is session-based with real ownership checks.** Every estate-scoped endpoint
  requires a session and verifies the caller owns that estate, except the seeded demo
  estate, which stays world-readable so a recruiter can click around without registering.
- **Every Claude and OpenAI call is traced.** Phoenix spans wrap the full agent loop
  (`estate_id`, rules checked, fallback used, tool calls); an LLM-as-judge eval
  (`agent/evals/deadline_next_steps_quality.py`) scores the DeadlineAgent's output quality
  on real traces. Tracing is optional and degrades to a harmless connection warning with
  no collector running — see [`agent/README.md`](agent/README.md#phoenix-tracing) to spin
  one up locally and actually watch the traces.
- **Two features are built but intentionally not exposed yet.** An email digest pipeline
  (Resend, human-toned templates, on-demand send) is fully working but gated behind a
  verified sending domain — see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#known-follow-up-email-delivery).
  A `ResearchAgent` prototype exists but currently relies on unofficial news search with no
  real relevance judgment and isn't wired to any trigger — a source-verified redesign
  (poll the actual CA statute/form pages this app's own rules cite, diff their amendment
  dates) is fully scoped in [`docs/RESEARCH_AGENT_REDESIGN.md`](docs/RESEARCH_AGENT_REDESIGN.md),
  not yet built.

## Stack

| | |
|---|---|
| **AI** | Anthropic Claude (parsing, agent reasoning, chat, letters) · OpenAI embeddings |
| **Backend** | Python · FastAPI · Pydantic v2 · bcrypt · Resend (email) |
| **Frontend** | Next.js 14 · TypeScript · Zod · Deepgram (voice) · Sentry |
| **Data** | Redis (KV + Redis 8 Vector Sets), Upstash, or in-memory — pluggable |
| **Observability** | Arize Phoenix tracing + LLM-as-judge evals |

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Node 18.18+.

```bash
make env       # copy .env examples (won't overwrite existing files)
make install   # uv sync for agent/, npm install for web/
make dev       # agent on :8000, web on :3000
make seed      # in a separate terminal: seed the demo estate
```

The only required key is `ANTHROPIC_API_KEY` in `agent/.env` — everything else (Redis,
Deepgram, Resend, Phoenix, Sentry) is optional and degrades gracefully when unset. See
[`agent/.env.example`](agent/.env.example) for the full list.

```bash
make test      # Python + TypeScript contract tests
make lint      # ruff (agent/) + ESLint (web/)
```

**Trying it out**: click "Try the demo" for the fastest path — no signup, seeded estate,
alerts already firing. To see the document-intelligence pipeline itself run end to end,
register a real account instead and upload a few files from
[`examples/`](examples/README.md) — it includes a numbered happy-path order and a note on
which document types the parser recognizes today.

## Deploying your own

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Render for the agent (a `render.yaml`
blueprint is included), Vercel for the frontend, one required env var on each side.

## Project structure

```
agent/     Python FastAPI service — routers, DeadlineAgent, document parsing, store
web/       Next.js frontend — dashboard, chat, voice, letters
docs/      Architecture, database contract, evaluation methodology, deployment
examples/  Sample estate documents for trying the upload pipeline
```

Read [`CLAUDE.md`](CLAUDE.md) for the full architecture map, and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for data shapes, the probate rule table, and
the demo scenario.

## Team

Built at UC Berkeley AI Hackathon 2026 by **Alex** (document intelligence), **Davyn** (data
layer & contracts), **Sameer** (DeadlineAgent & reasoning), and **Sherry** (frontend &
voice).

## License

[MIT](LICENSE)
