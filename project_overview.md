# Executor AI — Project Overview

## 1. The Product

Executor AI is an AI executor assistant that prevents executors from making
expensive legal and financial mistakes during estate administration. It parses estate
documents into a live intelligence graph and proactively alerts the executor *before*
deadline violations and liability triggers occur — not after.

The core insight: most AI products answer questions. ClearPath tells the executor what
they **don't know to ask**, before it costs them.

### One-sentence pitch
> "The AI that prevents executors from making expensive mistakes — by building a live
> intelligence graph of the estate and running a true agent that alerts before problems
> happen."

### The three capabilities (in build-priority order)
1. **Document Intelligence** — Upload a will, deed, bank statement, or insurance policy.
   Claude parses it into structured data (beneficiaries, assets, debts, dates, special
   instructions). Chunks are embedded and stored in Redis for semantic search; key facts
   are merged into a living estate-state graph in Redis KV.
2. **Estate-Aware Chat + Voice** — Every query runs a Redis vector search; retrieved
   chunks are injected into Claude's context. Answers are grounded in *this* estate's
   documents, not generic probate advice. Voice (Deepgram STT/TTS) makes it usable
   hands-free during phone calls with banks and institutions.
3. **DeadlineAgent (the moat)** — A genuine agent: it reads estate state, reasons over
   California probate statutes and liability triggers using Claude tool-use, and fires
   alerts ranked by urgency and consequence. It runs on demand and after every document
   upload. It does not wait to be asked.

---

## 2. Why This Stack (and Why Polyglot)

The previous plan was 100% TypeScript, including the agent. That was the wrong tool for
the agent and document-reasoning work, and it left a lot of sponsor value on the table.
This plan splits the system along its natural seam:

| Concern | Language | Why |
|---------|----------|-----|
| Document parsing, embeddings, the agent loop, RAG | **Python** | The richest ecosystem for LLM agents, structured extraction, and tracing/eval. Pydantic gives airtight Claude-output validation. Phoenix is the observability and evaluation surface. |
| Dashboard, chat UI, voice, presentation | **TypeScript / Next.js** | Best-in-class UI velocity, first-class Deepgram + Sentry SDKs, trivial SSE streaming to the browser. |
| Shared estate state + vectors | **Redis** | One source of truth both services read/write. Vector search + KV in one store ⇒ the Redis sponsor story is real, not "caching." |

The seam is clean: **Python is the brain, TypeScript is the experience, Redis is the
memory.** Each team member works mostly in one language.

### AI / LLM (Python `agent/`)
- **Anthropic Python SDK** (`anthropic`)
  - `claude-opus-4-8` — the DeadlineAgent's reasoning and the RAG chat. This is the
    "hard reasoning on a meaningful human problem" that the Anthropic prize rewards.
    Use **adaptive thinking** for the agent's multi-step deadline/liability analysis.
  - `claude-sonnet-4-6` — document parsing (vision + structured output) and letter
    drafting. Cheaper and fast for the higher-volume, lower-novelty calls.
  - **Structured extraction** via `messages.parse()` with Pydantic models — Claude output
    is validated into typed objects, never hand-parsed JSON.
  - **Vision / PDF** via document/image content blocks for scanned wills and statements.
  - **Prompt caching** on the (large, stable) estate-state system prompt so repeated chat
    turns and agent runs are cheap and fast.
  - **Tool-use loop** for the DeadlineAgent — Claude calls typed rule-evaluation tools and
    iterates until it has a complete, ranked alert set.
- **OpenAI embeddings** (`text-embedding-3-small`) for document chunks.

### Memory & vector store
- **Redis Cloud**. KV holds `estate:{id}`; Redis 8 Vector Sets hold embedded document
  chunks under `estate:{id}:chunks`, with chunk text/source stored as vector attributes.
  `text-embedding-3-small` produces 1536-dimensional vectors. This is **agent memory +
  retrieval**, which is exactly what the Redis prize asks for.

### Voice (TypeScript `web/`)
- **Deepgram** STT (executor speaks a question hands-free) and TTS (Claude's call-script
  is read aloud while the executor is on the phone with a bank). Voice is essential to the
  use case, not bolted on.

### Observability (two complementary layers)
- **Phoenix** traces the Python agent: every Claude call, OpenAI embedding call, and the full DeadlineAgent
  loop become spans with token counts, latency, and `estate_id` / `action_type`
  attributes. It is the natural trace and evaluation surface for the agent.
- **Sentry** instruments the Next.js layer (the proxy, voice routes, UI errors) and is the
  team-and-reliability story the Sentry prize rewards.

### Frontend (TypeScript `web/`)
- Next.js 14 App Router, TypeScript, Tailwind CSS. Streams chat from the Python service
  over SSE; talks to the agent only through a thin, typed, Sentry-wrapped client.

### Validation
- **Pydantic v2** in Python is the source of truth for every shape. **Zod + TS types** in
  `web/` mirror it for anything that crosses the wire. Member 2 owns the parity.

---

## 3. Target Tracks & Sponsors

### Main track
- **Ddoski's World (social impact).** Estate administration is a systemic-inequity
  problem: families without money for a probate attorney spend ~180 hours and make costly
  mistakes nobody warned them about. ClearPath gives them an expert in their corner. This
  is also squarely the Anthropic theme of "economic opportunity / shifting what's possible
  for people."

### Sponsor tracks we build *into the core* (focused, winnable)
| Sponsor | Prize | What must be true at demo |
|---------|-------|---------------------------|
| **Anthropic** | $5k API credits + office hours | Built with Claude; a true agent (DeadlineAgent) doing hard, proactive reasoning on a meaningful human problem. |
| **Redis** | Mac Minis + 25k cloud credits | Redis used as agent memory + vector retrieval, not caching. Redis Cloud KV holds the live state graph; Redis 8 Vector Sets power per-estate retrieval. |
| **Deepgram** | Nintendo Switch 2 / member | STT + TTS demonstrably essential — the executor uses voice during a simulated bank phone call. |
| **Sentry** | Nintendo Switch 2 / member | Observability on the web layer + a team that course-corrects under pressure. ~30 min of setup. |
| **Phoenix** | $1k | Phoenix tracing on the Python agent that *visibly improves the app* (catches a bad extraction / slow tool call during the build). |

### Deliberately out of scope (roadmap, not the hackathon)
- **Browserbase** (web-automation agent that looks up county-assessor property values),
  **Fetch.ai** (uAgents marketplace listing), **Orkes/Band** (multi-agent orchestration).
  All are real extensions of the agent, all add architectural risk a 24-hour demo won't
  reward. Mention them as the roadmap; do not build them.

---

## 4. Repository Structure

```
clearpath-estate/
├── CLAUDE.md
├── project_overview.md
├── hackathon_tracks_and_prizes.md
├── README.md
├── team/
│   ├── member1-document-intelligence.md
│   ├── member2-data-layer.md
│   ├── member3-deadline-agent.md
│   └── member4-frontend-chat-voice.md
│
├── agent/                          # Python FastAPI service — the brain
│   ├── main.py                     # FastAPI app + route wiring
│   ├── llm/
│   │   ├── claude.py               # Anthropic client + extract/stream/agent helpers
│   │   └── embeddings.py           # OpenAI embedding calls
│   ├── store/
│   │   └── redis_client.py         # Redis KV + vector helpers
│   ├── schemas/                    # Pydantic models (estate, alerts, extractions)
│   ├── documents/                  # Per-doc-type parsers + router
│   ├── agents/
│   │   └── deadline_agent.py       # The tool-use agent loop
│   ├── rules/
│   │   └── california_probate.py   # Hardcoded CA probate ruleset
│   ├── prompts/                    # System prompt, extraction, letter prompts
│   ├── observability/
│   │   └── phoenix.py              # Phoenix OTLP / OpenInference setup
│   └── seed/
│       └── demo_estate.py          # DEMO_ESTATE + reset
│
└── web/                            # Next.js frontend — the experience
    ├── app/
    │   ├── page.tsx                # Dashboard: overview + alerts + tasks
    │   ├── chat/page.tsx           # Estate-aware chat
    │   ├── upload/page.tsx         # Document upload
    │   └── api/
    │       ├── agent/[...path]/route.ts   # Sentry-wrapped proxy to Python
    │       └── voice/
    │           ├── transcribe/route.ts
    │           └── speak/route.ts
    ├── components/                 # Dashboard, AlertBanner, Chat, Voice, Upload, Letter
    ├── lib/                        # agentClient, deepgram, sentry, schemas (Zod)
    └── types/                      # TS types mirroring the Pydantic contract
```

---

## 5. Core Data Shapes

Defined as **Pydantic models** in `agent/schemas/`, mirrored as **TS types + Zod** in
`web/`. Field names are camelCase on the wire so both sides agree.

### EstateState — Redis KV key `estate:{id}`
```
id: str
deceasedName: str
dateOfDeath: str            # ISO date
appointmentDate: str        # ISO date — letters testamentary issued
state: "california"
executor: { name: str, email: str }
assets: Asset[]
debts: Debt[]
beneficiaries: Beneficiary[]
documents: UploadedDocument[]
tasks: Task[]
alerts: Alert[]
phase: 1 | 2 | 3 | 4 | 5 | 6
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
Each parser returns a typed extraction (e.g. `WillExtraction`, `BankStatementExtraction`,
`DeedExtraction`) carrying the structured facts plus `rawChunks: str[]` — 3–5 sentence
segments meant for embedding. Member 1 and Member 2 agree these shapes together.

---

## 6. California Probate Rules Database

The DeadlineAgent reasons against these hardcoded rules (`agent/rules/california_probate.py`).
This is the minimum viable ruleset for the hackathon.

| Rule | Trigger | Deadline | Consequence |
|------|---------|----------|-------------|
| DE-140 Probate Petition | Date of death known | File ASAP | No legal authority until filed |
| Death certificates | Date of death | Order 12+ immediately | Every institution requires one |
| DE-160 Inventory & Appraisal | Letters testamentary issued | 4 months | Court sanctions, personal liability |
| Creditor notification (certified mail) | Letters testamentary issued | 30 days | Personal liability for late distributions |
| Newspaper notice to creditors | First publication date | 3 consecutive weeks | §9052 violation |
| Creditor claim period closes | First publication date | 4 months | Cannot distribute before this |
| Estate EIN (IRS SS-4) | Before any banking | ASAP | Cannot open estate bank account |
| Final 1040 (personal) | Date of death | April 15 following year | IRS penalties |
| Form 1041 (estate income) | If estate earns >$600 | April 15 following year | Penalties — most executors miss this |
| Debt payment order | Before any distribution | Sequential | Out-of-order = personal liability |
| Property appraisal needed | Before DE-160 | Before 4-month deadline | Blocks inventory filing |

---

## 7. Core AI Flows

### Document parse (Python `agent/`)
```
Upload (PDF / image)
  → extract text (pypdf/pdfplumber) or pass image/PDF blocks to Claude vision
  → router detects document type
  → Sonnet 4.6 structured extraction → validated into a Pydantic model
  → Phoenix span { action: document_parse, doc_type }
  → embed rawChunks (OpenAI, 1536 dims) → upsert to Redis Vector Set `estate:{id}:chunks`
  → merge structured facts into estate state (Redis KV)
  → trigger DeadlineAgent to re-evaluate
  → return { extraction, alerts }
```

### Chat RAG (Python `agent/`, streamed to `web/`)
```
Message (typed, or Deepgram transcription)
  → embed query → Redis Vector Set search (top-k within `estate:{id}:chunks`)
  → load estate state from Redis KV
  → build cached system prompt: [base] + [estate state] + [retrieved chunks]
  → Opus 4.8 stream → SSE to the browser
  → if voice mode: web/ pipes text to Deepgram TTS
  → Phoenix span { action: chat_query }
```

### DeadlineAgent (Python `agent/` — the moat)
```
Triggered on demand or after every parse
  → load estate state
  → Claude tool-use loop (Opus 4.8, adaptive thinking):
       Claude calls typed rule-evaluation tools over california_probate rules,
       computes days_remaining (dateutil), decides severity, dedupes,
       and reasons about cross-rule consequences (e.g. appraisal blocks DE-160)
  → produce ranked Alert[] (critical first)
  → write alerts back to Redis KV
  → Phoenix span { action: deadline_agent_run, rules_checked, alerts_fired }
  → return alerts
```

### Letter generation (Python `agent/`)
```
Letter type (e.g. "Wells Fargo estate notification")
  → load estate state → select letter prompt → inject estate-specific variables
  → Sonnet 4.6 drafts a formatted, sign-ready letter
  → Phoenix span { action: letter_generation, letter_type }
  → return draft to LetterPreview in web/
```

---

## 8. System Prompt Template

The base system prompt for chat (`agent/prompts/`), assembled per request and prompt-cached
on the stable prefix:

```
You are an estate administration assistant helping an executor manage the estate of
{deceasedName}, who passed away on {dateOfDeath}. The executor is {executorName}.

This estate is in California. Letters testamentary were issued on {appointmentDate},
meaning the executor has had legal authority since that date.

ESTATE STATE:
{estateStateJSON}

RETRIEVED DOCUMENT CONTEXT:
{retrievedChunks}

RULES YOU MUST FOLLOW:
- Answer from the estate state and documents above, not generic probate advice.
- When citing a deadline, always include the exact date and the consequence of missing it.
- If you don't have a fact (e.g. a missing account number), say so explicitly.
- Never give legal advice. For attorney-judgment questions, say:
  "This requires your attorney's input — it involves [reason]."
- Keep tone warm and direct. This person is grieving. Never be clinical.
- If overwhelm is detectable, surface only the single most urgent next action.
- Always answer in plain English. Define any legal term you use.
```

---

## 9. Demo Scenario

Seed this fictional estate for a reliable, emotionally resonant demo.

```
DEMO_ESTATE  (id: demo-milligan)
  deceasedName:    Robert A. Milligan
  dateOfDeath:     2026-06-03
  appointmentDate: 2026-06-10
  state:           california
  executor:        Dana Milligan <dana@demo.com>

  assets:
    real_estate    1847 Marin Ave, Berkeley CA   ~$220,000   appraised: false
    bank_account   Wells Fargo checking …4412     $38,240
    retirement     Fidelity IRA …7731             $26,500    beneficiaryNamed: true
    vehicle        2019 Honda Civic               ~$12,000    appraised: false

  debts:
    UCSF Medical Center     $4,200    unsecured   notified: false
    Chase Visa              $3,100    unsecured   notified: false
    First Republic Mortgage $141,000  secured     notified: false

  beneficiaries:
    Dana Milligan 40% · Sarah Milligan 40% · Marcus Milligan 20%

  phase: 2
```

Designed to fire two CRITICAL alerts live:
1. DE-160 Inventory & Appraisal due ~9 days out, no property appraisal uploaded.
2. Creditors not yet notified — the 30-day window from June 10 nearly elapsed.

A `POST /seed` endpoint resets this to a known-good state between demo runs.

---

## 10. Hackathon Build Order

| Hours | What to build | Why first |
|-------|---------------|-----------|
| 0–1 | Repo skeleton: `agent/` FastAPI + `web/` Next.js + Redis connectivity | Both services must boot and reach Redis |
| 0–2 | Contracts: Pydantic models + mirrored TS/Zod types + seed data | Everyone codes against the same shapes |
| 1–5 | Claude document extraction → embed → Redis (Python) | Foundation everything runs on |
| 2–5 | Redis vector + KV helpers; seed reset endpoint | Enables RAG and the agent |
| 5–9 | RAG chat (Python SSE) + chat UI (web) | First demo-worthy moment |
| 9–14 | DeadlineAgent tool-use loop + rules engine | The actual product moat |
| 12–16 | Dashboard + AlertBanner (the hero component) | Proactive intelligence made visible |
| 14–17 | Deepgram voice (STT + TTS) | Emotional demo hook; wins the track |
| 16–18 | Phoenix + Sentry instrumentation | Two complementary observability layers; low effort |
| 18–22 | Letter generation + polish | Completes the story |
| 22–24 | Demo rehearsal, edge cases, seed reset drills | Ship something that works reliably |

---

## 11. Positioning

**Before ClearPath:** Dana spends 180 hours, makes three costly mistakes, pays $4,200 in
unexpected fees, and nobody ever told her the rules that would have prevented all of it.

**After ClearPath:** Dana uploads three documents. The AI reconstructs her estate. The
agent tells her the next three actions. It catches the mistake before it happens.

Every architectural decision serves that story. Nothing that doesn't serve it gets built
at the hackathon.
