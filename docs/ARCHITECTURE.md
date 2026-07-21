# Architecture

## System Overview

Two services sharing one Redis-backed state store — each language doing what it's best at,
not collapsed into one stack for its own sake:

```
┌────────────────────────┐         ┌─────────────────────────────┐
│  web/  (TypeScript)     │  HTTP   │  agent/  (Python)            │
│  Next.js 14 frontend    │ ──────▶ │  FastAPI "brain"             │
│  • Dashboard / chat UI  │  SSE    │  • Auth (login / register)   │
│  • Deepgram voice       │ ◀────── │  • Document intelligence     │
│  • Sentry observability │         │  • RAG chat (streaming)      │
└───────────┬─────────────┘         │  • DeadlineAgent (tool-use)  │
            │                       │  • ResearchAgent (prototype) │
            │                       │  • Letter gen · Email (Resend)│
            │                       │  • Phoenix tracing + evals   │
            │                       └──────────────┬──────────────┘
            │        Redis (KV estate state + vector search)        │
            └───────────────────────┬──────────────────────────────┘
                                    ▼
              Redis Cloud (KV + Redis 8 Vector Sets)
               (Upstash / in-memory backends also supported)
```

- **Python (`agent/`)** owns all Claude reasoning, document parsing, embeddings, the agent
  loop, and RAG.
- **TypeScript (`web/`)** owns everything the user sees and touches, plus voice.
- **Redis is the only thing both services talk to.** It's the contract between them — the
  browser never calls the Python service directly; every request is proxied through Next.js,
  which forwards the session as a bearer token server-side, so there's no CORS surface at all.

### Stack

| | |
|---|---|
| **`agent/`** | FastAPI + Uvicorn, Python 3.11+ · Anthropic SDK · OpenAI embeddings (`text-embedding-3-small`, 1536-dim) · Pydantic v2 · bcrypt sessions · Phoenix tracing · `pdfplumber` + Claude vision for documents |
| **`web/`** | Next.js 14 App Router, TypeScript · Zod (mirrors the Pydantic contract) · Deepgram (voice) · Sentry |
| **Store** | `agent/store/` supports three interchangeable backends behind one API, selected by `STORE_BACKEND`: `redis_cloud` (Redis Cloud KV + Redis 8 Vector Sets), `upstash` (Upstash Redis REST + Upstash Vector), and `memory` (in-process, zero setup — the default) |

The model used throughout `agent/` today is `claude-sonnet-4-6` (`agent/llm/claude.py`
exposes `DOCUMENT_MODEL` and `REASONING_MODEL`, both currently pointed at it) — swap
`REASONING_MODEL` to `claude-opus-4-8` for a heavier reasoning path on the DeadlineAgent if
wanted.

## Production Deployment

The live app (linked from the README) runs on real, separately-provisioned cloud
infrastructure — not a single "click deploy" default, and not the same thing as the local
dev setup above. Both halves auto-deploy independently on every push to `main`:

```
GitHub (main)
  │
  ├─ agent/** or cloudbuild.yaml changed
  │     └──▶ Cloud Build trigger (path-scoped) ──▶ docker build (agent/Dockerfile)
  │                                                        │
  │                                                        ▼
  │                                          Artifact Registry (image, tagged by commit SHA)
  │                                                        │
  │                                                        ▼
  │                                    Cloud Run: probatepilot-agent
  │                                    scale-to-zero · dedicated least-privilege IAM SA
  │
  └─ web/ changed
        └──▶ Vercel Git integration (path-scoped) ──▶ next build ──▶ Vercel: probatepilot

                    Redis Cloud (KV + Vector Sets) — independent of both deploy paths,
                    reached over the network via REDIS_URL regardless of what's hosting
                    the agent (Cloud Run today; identical story on Render or a laptop)
```

- **Cloud Run runs the exact same `agent/Dockerfile` used for local dev** — no separate
  "production" build to drift out of sync. Deploys under a dedicated service account
  (`probatepilot-deploy`) holding exactly four roles it needs — `run.admin`,
  `iam.serviceAccountUser`, `artifactregistry.writer`, `logging.logWriter` — rather than
  the default Cloud Build service account's much broader `Editor`-equivalent access.
  Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `REDIS_URL`) are never written into
  `cloudbuild.yaml`, which is committed and public: `gcloud run deploy` bases each new
  revision on the currently-serving revision's config and only overrides what's explicitly
  passed, so they're set once and simply carry forward on every automated redeploy —
  verified by inspecting the env vars on a revision the pipeline deployed automatically,
  not assumed from documentation.
- **Cold start, measured on the real deployed service, not assumed from Cloud Run's
  reputation:** 13.99 seconds after 12 minutes idle. Still a real win over the equivalent
  measurement on a Render free-tier deploy (~30-60s, the documented alternative in
  `docs/DEPLOYMENT.md`), but stated as what was actually measured rather than rounded up
  to "near-instant."
- **Both pipelines are scoped by path, independently, and both directions are verified —
  not just configured and assumed to work.** Cloud Build's trigger has an
  `includedFiles: [agent/**, cloudbuild.yaml]` filter; Vercel's project has "skip
  deployments when there are no changes to the root directory" enabled. A docs-only commit
  (touching neither `agent/` nor `web/`) was pushed specifically to confirm neither
  pipeline fired — it didn't.
- **Redis Cloud is fully decoupled from the compute layer.** The agent holds nothing more
  than a `REDIS_URL` connection string; persistence has no dependency on which platform is
  currently running the container.
- **A weekly Cloud Scheduler job (`probatepilot-redis-keepalive`) prevents a real, documented
  risk**: Redis Cloud's free tier deletes a database after 14 consecutive days with no read
  or write commands (per Redis's own SLA/AUP), which a portfolio deploy's sporadic traffic
  could genuinely hit. It targets the already-unauthenticated `GET /estate/demo-milligan` —
  a plain Redis read, deliberately not `/seed`, which would also run a real (small but
  nonzero) Claude API call every week for no benefit to the actual goal.
- **The two deploy pipelines aren't equally resilient to a GitHub repo rename, and that
  difference was found by testing, not assumed.** After renaming the repo, Cloud Build's
  auto-deploy silently stopped firing entirely (confirmed: a real push produced zero new
  builds) — its `repository` resource had cached the *old* URL with no `update` command to
  fix it in place, only delete-and-recreate. Vercel's equivalent pipeline needed no
  intervention at all; a push right after the same rename produced a new deployment
  correctly aliased under the standard git-triggered pattern
  (`probatepilot-git-main-*.vercel.app`), confirming it tracks the connected repo more
  robustly than Cloud Build's resource model does.

Full setup — every command, every IAM grant, and every real gotcha hit doing this end to
end (a GitHub App silently scoped to a differently-named repository, an ARM64/amd64 image
mismatch specific to building on Apple Silicon, a monorepo `Root Directory` config that
broke CLI redeploys after a dashboard-based reconnect, two separate Cloud Build CLI
operations that failed with an opaque error where the Console GUI succeeded on the first
try, and the repo-rename/webhook issue above) — is documented in
[`docs/DEPLOYMENT.md`](DEPLOYMENT.md), written from what actually happened rather than an
idealized run-through.

## Project Layout

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
| ResearchAgent (prototype, not wired to a trigger — see `docs/RESEARCH_AGENT_REDESIGN.md`) | `agent/researcher/research_agent.py` |
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

## API Reference

Every route below except `/health`, `/seed`, and `/auth/*` requires a session and estate
ownership (`api/deps.py::ensure_estate_access`) — the one standing exception is the canonical
seeded estate (`demo-milligan`), which stays world-readable for `/seed`-based testing and
curl access without a session.

### Python `agent/` (FastAPI)

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Service status + Phoenix/instrumentor readiness |
| `/auth/register` · `/auth/login` · `/auth/logout` | POST | Account + cookie session |
| `/auth/demo` | POST | Guest session on its own throwaway copy of the seed estate — every call mints an independent `demo-{uuid}` estate + user (self-expiring), so one visitor's edits never show up for another |
| `/auth/me` | GET | Current authenticated user |
| `/estates` | POST | Create a real estate shell |
| `/estate/{estate_id}` | GET | Fetch full estate state |
| `/seed` | POST | Reset the canonical demo estate to a known-good state |
| `/parse-document` · `/parse-documents` | POST | Upload(s) → Claude extract → embed → store |
| `/document/{estate_id}/{doc_id}` | GET / DELETE | Fetch or remove an uploaded document |
| `/deadline-agent` | POST | Run the full Claude-enhanced agent loop → return ranked alerts |
| `/research-agent` | POST | Prototype news-search pass → review alerts (see `docs/RESEARCH_AGENT_REDESIGN.md`) |
| `/complete-alert` | POST | Mark an alert/step done → updated estate |
| `/chat` | POST | Message → RAG retrieve → Claude stream (SSE) |
| `/chat-history/{estate_id}` · `/chat-sessions/{estate_id}` | GET / POST | Chat persistence |
| `/chat-suggestions` | POST | Suggested follow-up questions |
| `/generate-letter` · `/save-letter` | POST | Draft / persist a letter |
| `/letter/{estate_id}/{letter_id}` | DELETE | Remove a saved letter |
| `/notify/email` | POST | Send weekly recap / alert digest via Resend (UI gated — see `docs/DEPLOYMENT.md`) |

### TypeScript `web/` (Next.js route handlers)

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/auth/{login,logout,register,me}` | * | Auth proxied to the Python service |
| `/api/voice/transcribe` | POST | Audio → Deepgram STT → text |
| `/api/voice/speak` | POST | Text → Deepgram TTS → audio |
| `/api/agent/*` | * | Thin Sentry-wrapped proxy to the Python service |

## Core Data Shapes

The contract: defined once as **Pydantic models** in `agent/schemas/`, mirrored as **TypeScript types +
Zod schemas** in `web/`. Field names are camelCase on the wire so both sides agree without
translation.

### EstateState — Redis KV key `estate:{id}`

```
id: str
deceasedName: str
dateOfDeath: str            # ISO date
appointmentDate: str        # ISO date — letters testamentary issued
state: "california"
county: str?                # e.g. "Alameda"
executor: { name: str, email: str }
assets: Asset[]
debts: Debt[]
beneficiaries: Beneficiary[]
documents: UploadedDocument[]
tasks: Task[]
alerts: Alert[]
letters: SavedLetter[]      # drafts saved to the estate
phase: 1 | 2 | 3 | 4 | 5 | 6
isDemo: bool                # true for demo-{uuid} estates — see Demo Scenario below
createdAt: str
updatedAt: str
```

### Asset / Debt / Beneficiary

```
Asset:        id, type(real_estate|bank_account|retirement|vehicle|personal_property|
               other), description, estimatedValue?, appraised: bool, appraisedValue?,
               beneficiaryNamed?
Debt:         id, creditor, amount, type(secured|unsecured|priority),
               notified: bool, notifiedDate?, claimFiled?
Beneficiary:  id, name, share?, specificBequest?, contactInfo?
```

### Alert — output of the DeadlineAgent

```
id: str
severity: critical | warning | info
type: deadline | liability | missing_doc | rule_violation
title: str                  # "DE-160 filing due in 9 days"
body: str                   # full explanation with the consequence
rule: str                   # the specific statute / rule triggered
daysRemaining?: int
actionRequired: str         # the single next action
createdAt: str
dismissed: bool
```

### Document extraction (Claude output, one per doc type)

Each parser returns a typed extraction (`WillExtraction`, `BankStatementExtraction`,
`DeedExtraction`, `CreditorNoticeExtraction`) carrying the structured facts plus
`rawChunks: str[]` — short segments meant for embedding. Defined in
`agent/schemas/documents.py`.

---

## California Probate Rules

The DeadlineAgent reasons against a deterministic rule table
(`agent/rules/california_probate.py`) before Claude ever sees the estate — every rule below
is a pure function of `EstateState`, no LLM required to fire it.

| Rule | Trigger | Deadline | Consequence |
|------|---------|----------|-------------|
| DE-111 Probate Petition (§8000) | Date of death known | File ASAP | No legal authority until filed |
| Death certificates | Date of death | Order immediately | Every institution requires one |
| Letters Testamentary | Petition filed | After court appointment | Blocks all downstream administration |
| DE-160 Inventory & Appraisal | Letters testamentary issued | 4 months | Court sanctions, personal liability |
| Creditor notification (certified mail, §9051) | Letters testamentary issued | 30 days | Personal liability for late distributions |
| State agency notice (Medi-Cal/DHCS, FTB, Victim Comp, child support, §9202) | Letters testamentary issued | 90 days | Personal liability, especially Medi-Cal estate recovery |
| Estate EIN (IRS SS-4) | Legal authority granted | ASAP | Cannot open estate bank account |
| Estate bank account | EIN obtained | ASAP | Estate funds must stay separate from personal funds |
| Debt resolution (§11420) | Creditor notice sent | Before distribution | Unresolved debts can block final distribution |
| Final 1040 (personal) | Date of death | April 15 following year | IRS penalties |
| Debt payment order (§11420) | Any debt notified | Secured before unsecured/priority | Out-of-order payment = personal liability |
| Petition for final distribution (§12200) | Letters testamentary issued | 1 year (18 months with a federal estate tax return) | Court can compel via order to show cause |

Three more rules are real CA probate requirements the schema can't evaluate yet — newspaper
notice (§8121, form DE-121), the creditor claim-period close (§9100), and Form 1041 — each
needs a field (`firstPublicationDate`, `estateIncome`) `EstateState` doesn't track today.
They're documented, not silently stubbed, directly above `CALIFORNIA_PROBATE_RULES` in the
source.

**Debt payment order** is worth calling out: CA probate pays secured creditors before
unsecured or priority ones, before any beneficiary distribution. There's no explicit
"payment status" field on `Debt`, but `notified` is real tracked state — so the rule fires
the moment an unsecured or priority creditor has been notified while a secured creditor
hasn't, the earliest observable sign the order is being violated.

---

## Core AI Flows

### Document parse (`agent/`)

```
Upload (PDF / image)
  → extract text (pdfplumber) or pass image/PDF blocks to Claude vision
  → router detects document type (keyword match, filename fuzzy-match, or Claude)
  → structured extraction → validated into a Pydantic model
  → Phoenix span { action: document_parse, doc_type }
  → embed rawChunks (OpenAI 1536-dim, or a hashing-trick fallback if unconfigured)
    → upsert to the vector store, scoped to estate:{id}
    → a vector-store failure (e.g. Redis without Vector Sets support) is caught here —
      logged and traced, not fatal; the document is saved either way, just not
      searchable via chat until the store issue is fixed
  → merge structured facts into estate state (Redis KV)
  → trigger DeadlineAgent to re-evaluate
  → return { extraction, alerts }
```

### Chat RAG (`agent/`, streamed to `web/`)

```
Message (typed, or Deepgram transcription — the mic tells you plainly if
  DEEPGRAM_API_KEY isn't set, via a 503 from /api/voice/*, instead of failing silently)
  → embed query → vector search (top-k within the estate's chunks)
  → load estate state from Redis KV
  → build system prompt: [base] + [estate state] + [retrieved chunks]
  → Claude stream → SSE to the browser
  → if voice mode: web/ pipes text to Deepgram TTS
  → Phoenix span { action: chat_query }
```

### DeadlineAgent — the differentiator

```
Triggered on demand or after every parse
  → evaluate the deterministic CA probate rules against estate state (always runs first —
    this alone produces a complete, correct alert set with zero LLM involvement)
  → Claude tool-use loop: read-only tools expose the rule catalog and rule evaluator, plus
    a forced submit_deadline_alerts tool
  → Claude may only rewrite alert copy (title/body/actionRequired/steps) — it cannot drop,
    invent, or reorder the deterministic alerts. If Claude's output fails validation, the
    deterministic alerts win outright.
  → write alerts back to Redis KV
  → Phoenix span { action: deadline_agent_run, rules_checked, alerts_fired, fallback_used }
  → return ranked alerts (critical first)
```

This "deterministic core, LLM as copywriter" design means the agent never loses on
correctness to a bad model response — a missing `ANTHROPIC_API_KEY` or a malformed Claude
reply both fall back to the same rule-evaluated alerts, just with plainer wording.

### Letter generation (`agent/`)

```
Letter type (e.g. "Wells Fargo estate notification")
  → load estate state → select letter prompt → inject estate-specific facts
  → Claude drafts a formatted, sign-ready letter (deterministic fallback if unconfigured)
  → Phoenix span { action: letter_generation, letter_type }
  → return draft to the Letters screen in web/
```

---

## System Prompt (chat)

The system prompt (`agent/prompts/system.py`) is assembled per request from a fixed
instruction block (`BASE_CHAT_SYSTEM_PROMPT`) plus the estate's actual facts, in this exact
order:

```
[BASE_CHAT_SYSTEM_PROMPT — identical text every request, see below]
You are helping {executorName} manage the estate of {deceasedName}, who passed away on
{dateOfDeath}.

This estate is in {state}. Letters testamentary were issued on {appointmentDate}, meaning
the executor has had legal authority since that date.

DECEASED NAME:
{deceasedName}

DATE OF DEATH:
{dateOfDeath}

EXECUTOR NAME:
{executorName}

APPOINTMENT DATE:
{appointmentDate}

ESTATE STATE JSON:
{estateStateJSON}

RETRIEVED DOCUMENT CONTEXT:
{retrievedChunks}
```

`BASE_CHAT_SYSTEM_PROMPT`, the fixed block at the top:

```
You are an estate administration assistant helping an executor manage a California estate.

RULES YOU MUST FOLLOW:
- California probate only.
- Answer from the estate state and retrieved documents below, not generic probate advice.
- When citing a deadline, always include the exact date and the consequence of missing it.
- If you do not have a fact, such as an account number, filing date, publication date, or
  document status, say so explicitly.
- Never give legal advice. For attorney-judgment questions, say exactly:
  "This requires your attorney's input — it involves [reason]."
- You may still explain operational next steps, deadlines, documents to gather, and what
  information is missing.
- Keep tone warm and direct. This person is grieving. Never be clinical.
- If the user sounds overwhelmed, surface only the single most urgent next action.
- Always answer in plain English. Define any legal term you use.
```

On the live Claude path this is sent as two Anthropic content blocks, not one string
(`build_chat_system_blocks()`): `BASE_CHAT_SYSTEM_PROMPT` carries a `cache_control:
{"type": "ephemeral"}` marker since it's identical on every request, and the estate
facts/retrieved-chunks block stays uncached since it changes per request.
`build_chat_prompt()` (a single concatenated string) still exists for tests and
offline/debug use.

**Caveat, verified against the live API, not assumed:** Anthropic only caches a block
once it clears a minimum size (1024 tokens for Sonnet/Opus, 2048 for Haiku) — below that
the `cache_control` marker is accepted but silently does nothing. `BASE_CHAT_SYSTEM_PROMPT`
is ~230 tokens, so on today's prompt the chat cache does not actually activate
(`cache_creation_input_tokens` / `cache_read_input_tokens` both measured at 0 across
repeat calls). The marker is harmless and forward-compatible — it starts working the
moment the prefix grows past the threshold (e.g. if the rules block or few-shot examples
are expanded) — but as written today it's a no-op in practice, not a real saving.

The DeadlineAgent's system prompt (`DEADLINE_AGENT_SYSTEM_BLOCKS` in
`agent/agents/deadline_agent.py`) is cached the same way, and here it does activate: the
system prompt plus the tool definitions that precede it in the request (`DEADLINE_AGENT_TOOLS`
+ `DEADLINE_ALERT_SUBMISSION_TOOL`, which embeds the full `Alert` JSON schema) total
~1,066 tokens, above the threshold. Measured directly against the API: the first call in
a run shows `cache_creation_input_tokens=1066` (cache write), and a repeat call with the
identical prefix shows `cache_read_input_tokens=1066` (cache hit) — a real saving, reused
up to `MAX_TOOL_ROUNDS` (5) times per agent run since the tool loop calls Claude
repeatedly with the same static prefix.

---

## Demo Scenario

`POST /seed` resets the canonical `demo-milligan` record (used for testing/curl access) to a
known-good state. The "Try the demo" button is separate: each click
(`build_demo_estate_for_visitor()`) copies this same seed content into a fresh, independent
`demo-{uuid}` estate plus a throwaway user, so visitors never share or reset each other's
progress. Both self-expire via a Redis TTL (`DEMO_VISITOR_TTL_SECONDS`, `agent/constants.py`)
that renews on every write, so abandoned sessions clean themselves up without a cron job.
Login itself only runs `refresh_deadline_state()` (deterministic rules, no Claude call) so
the dashboard populates instantly; the full Claude-enhanced pass runs afterward in the
background. The canonical seed content, defined in `agent/seed/demo_estate.py`:

```
demo-milligan
  deceasedName:    Robert A. Milligan
  dateOfDeath:     2026-06-03
  appointmentDate: 2026-06-10
  executor:        Dana Milligan

  assets:
    real_estate    1847 Marin Ave, Berkeley CA   ~$220,000   appraised: false
    bank_account   Wells Fargo checking …4412     $38,240    appraised: true
    retirement     Fidelity IRA …7731             $26,500    beneficiaryNamed: true
    vehicle        2019 Honda Civic               ~$12,000    appraised: false

  debts:
    UCSF Medical Center     $4,200    unsecured   notified: false
    Chase Visa              $3,100    unsecured   notified: false
    First Republic Mortgage $141,000  secured     notified: false

  beneficiaries:
    Dana Milligan 40% · Sarah Milligan 40% · Marcus Milligan 20%

  documents: seeded will, Wells Fargo statement, grant deed, letters testamentary
  tasks:     phase-1 items done (petition, death certs, EIN); phase-2 open
             (notify creditors, prepare DE-160)
  phase: 2
```

This fires three CRITICAL alerts on load (exact day counts depend on the run date):

1. **Creditors not yet notified** — the 30-day certified-mail window from the June 10
   appointment is closing.
2. **State agencies not yet notified** — Medi-Cal/DHCS, FTB, Victim Compensation, and child
   support all have a 90-day window from appointment (CA Probate Code §9202); Medi-Cal
   estate recovery in particular is a real, common personal-liability trap.
3. **DE-160 Inventory & Appraisal outstanding** — no appraisal on the Berkeley home or the
   Honda Civic.
