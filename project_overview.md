# ClearPath Estate — Project Overview

## Project Overview

ClearPath Estate is an AI executor assistant that prevents executors from making expensive legal and financial mistakes during estate administration. The system parses estate documents into a live intelligence graph and proactively alerts the executor before deadline violations and liability triggers occur — not after.

The core product insight: most AI products answer questions. ClearPath tells users what they don't know to ask, before it costs them.

### One-Sentence Pitch

> "The AI that prevents executors from making expensive mistakes — by building a live intelligence graph of the estate and alerting before problems happen."

### The Three Capabilities (in build priority order)

1. **Document Intelligence** — Upload a will, deed, bank statement, or insurance policy. Claude parses it into structured JSON (beneficiaries, assets, debts, dates, special instructions). Extracted chunks are embedded into Redis Iris for semantic search. Key facts are written to Redis KV as a living estate state graph.

2. **Estate-Aware Chat + Voice** — Every chat query triggers a Redis vector search, retrieving relevant document chunks injected into Claude's context. Answers are grounded in this specific estate's documents, not generic probate advice. Voice interface via Deepgram STT/TTS for hands-free use during phone calls with institutions.

3. **DeadlineAgent (the core differentiator)** — A background rules engine that reads estate state, compares it against California probate statutes and liability triggers, and fires proactive alerts ranked by urgency and consequence. Runs on a scheduled trigger. Does not wait for the executor to ask.

---

## Tech Stack

### AI & LLM

- **Anthropic Claude** (`claude-sonnet-4-6`) — Primary reasoning engine for document parsing, RAG-based chat, rules reasoning in DeadlineAgent, and letter/document generation
  - Use structured output / JSON mode for document extraction
  - Use streaming for chat responses
  - Vision capability for PDF and image document parsing
  - SDK: `@anthropic-ai/sdk`

- **OpenAI Embeddings** (`text-embedding-3-small`) — Generate vector embeddings for document chunks stored in Redis Iris
  - SDK: `openai`

### Memory & Vector Store

- **Redis** (via Upstash or Redis Cloud)
  - **Redis Iris** — Vector index for semantic search over embedded estate document chunks
  - **Redis KV** — Estate state graph (assets, debts, beneficiaries, deadlines, tasks) and conversation session memory
  - SDK: `ioredis` or `@upstash/redis`
  - Vector search: `@upstash/vector` or `redis` with vector commands

### Voice

- **Deepgram** — Speech-to-text (STT) and text-to-speech (TTS)
  - STT: Real-time transcription of executor voice input
  - TTS: Reading Claude responses aloud during phone call scripts
  - SDK: `@deepgram/sdk`

### Observability

- **Sentry** — Distributed tracing and error monitoring for every agent action
  - Wrap every Claude call, every DeadlineAgent run, and every document extraction in Sentry transactions
  - Custom tags: `estate_id`, `action_type`, `rule_checked`, `agent_name`
  - SDK: `@sentry/nextjs`

### Frontend

- **Next.js 14** (App Router) — Primary web application
- **TypeScript** — All source files
- **Tailwind CSS** — Styling
- **Vercel AI SDK** (`ai`) — Streaming chat UI components and Claude integration helpers

### Document Processing

- **pdf-parse** — Extract text from uploaded PDF documents
- **sharp** — Image preprocessing before sending to Claude Vision
- **formidable** — Handle multipart file uploads in Next.js API routes

### Backend / API

- **Next.js API Routes** — All server-side logic including document parsing, chat, DeadlineAgent, and letter generation endpoints
- **Zod** — Runtime validation of Claude structured output and API request/response schemas

### Scheduling (DeadlineAgent)

- **Vercel Cron Jobs** — Trigger DeadlineAgent on a schedule (every hour during demo, configurable)
  - Or: `node-cron` if running a standalone Node server

### Utilities

- **date-fns** — Date arithmetic for deadline calculations (days from appointment date, statutory windows)
- **nanoid** — Generate estate IDs and session IDs
- **dotenv** — Environment variable management locally

---

## Project Structure

```
clearpath-estate/
├── CLAUDE.md                        # This file
├── .env.local                       # API keys (never commit)
├── .env.example                     # Template for env vars
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
│
├── app/
│   ├── layout.tsx
│   ├── page.tsx                     # Dashboard — estate overview, alerts, tasks
│   ├── chat/
│   │   └── page.tsx                 # Estate-aware chat interface
│   ├── upload/
│   │   └── page.tsx                 # Document upload UI
│   └── api/
│       ├── parse-document/
│       │   └── route.ts             # POST: upload doc → Claude extracts → Redis stores
│       ├── chat/
│       │   └── route.ts             # POST: message → Redis RAG → Claude → stream response
│       ├── voice/
│       │   ├── transcribe/
│       │   │   └── route.ts         # POST: audio blob → Deepgram STT → text
│       │   └── speak/
│       │       └── route.ts         # POST: text → Deepgram TTS → audio stream
│       ├── deadline-agent/
│       │   └── route.ts             # GET: run rules engine against estate state → alerts
│       ├── generate-letter/
│       │   └── route.ts             # POST: letter type + estate state → Claude → draft
│       └── cron/
│           └── deadline-check/
│               └── route.ts         # Vercel cron endpoint — triggers DeadlineAgent
│
├── lib/
│   ├── claude.ts                    # Anthropic client + helper functions
│   ├── redis.ts                     # Redis client (vector + KV)
│   ├── deepgram.ts                  # Deepgram client + STT/TTS helpers
│   ├── sentry.ts                    # Sentry transaction wrappers
│   ├── embeddings.ts                # OpenAI embedding generation
│   │
│   ├── agents/
│   │   └── deadline-agent.ts        # Rules engine — reads estate state, fires alerts
│   │
│   ├── parsers/
│   │   ├── will-parser.ts           # Claude prompt + schema for will extraction
│   │   ├── bank-statement-parser.ts # Claude prompt + schema for bank statement extraction
│   │   ├── deed-parser.ts           # Claude prompt + schema for deed extraction
│   │   └── document-router.ts      # Detect document type → route to right parser
│   │
│   ├── rules/
│   │   └── california-probate.ts    # Hardcoded CA probate rules, deadlines, liability triggers
│   │
│   ├── prompts/
│   │   ├── system-prompt.ts         # Base estate-aware system prompt with state injection
│   │   ├── extraction-prompts.ts    # Per-document-type extraction prompts
│   │   └── letter-prompts.ts        # Letter generation prompts (creditor, bank, IRS, etc.)
│   │
│   └── schemas/
│       ├── estate-state.ts          # Zod schema for the full estate state object
│       ├── document-extractions.ts  # Zod schemas per document type
│       └── alerts.ts                # Zod schema for DeadlineAgent alert objects
│
├── components/
│   ├── EstateOverview.tsx           # Summary stats — assets, debts, deadline countdown
│   ├── AlertBanner.tsx              # Proactive DeadlineAgent alerts (the hero feature)
│   ├── ChatInterface.tsx            # Streaming chat with voice toggle
│   ├── DocumentUpload.tsx           # Drag-and-drop upload with parsing status
│   ├── TaskList.tsx                 # Phase-gated task checklist
│   ├── LetterPreview.tsx            # Generated letter with approve/edit/copy
│   └── VoiceButton.tsx              # Hold-to-speak Deepgram integration
│
└── types/
    ├── estate.ts                    # TypeScript types for estate state, assets, debts
    ├── alerts.ts                    # Alert severity, type, and content types
    └── documents.ts                 # Document type unions and extraction output types
```

---

## Environment Variables

```bash
# .env.local — never commit this file

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (embeddings only)
OPENAI_API_KEY=sk-...

# Redis (Upstash recommended for serverless)
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...
UPSTASH_VECTOR_REST_URL=https://...
UPSTASH_VECTOR_REST_TOKEN=...

# Deepgram
DEEPGRAM_API_KEY=...

# Sentry
SENTRY_DSN=https://...
NEXT_PUBLIC_SENTRY_DSN=https://...
SENTRY_ORG=...
SENTRY_PROJECT=...

# App
NEXT_PUBLIC_APP_URL=http://localhost:3000
CRON_SECRET=...   # Secret to validate Vercel cron requests
```

---

## Key Data Schemas

### Estate State (Redis KV — key: `estate:{id}`)

```typescript
interface EstateState {
  id: string
  deceasedName: string
  dateOfDeath: string           // ISO date
  appointmentDate: string       // Date letters testamentary issued
  state: "california"           // Jurisdiction — CA rules hardcoded for hackathon
  executor: {
    name: string
    email: string
  }
  assets: Asset[]
  debts: Debt[]
  beneficiaries: Beneficiary[]
  documents: UploadedDocument[]
  tasks: Task[]
  alerts: Alert[]
  phase: 1 | 2 | 3 | 4 | 5 | 6
  createdAt: string
  updatedAt: string
}
```

### Alert (output of DeadlineAgent)

```typescript
interface Alert {
  id: string
  severity: "critical" | "warning" | "info"
  type: "deadline" | "liability" | "missing_doc" | "rule_violation"
  title: string                 // Short: "DE-160 filing due in 9 days"
  body: string                  // Full explanation with consequence
  rule: string                  // The specific statute or rule triggered
  daysRemaining?: number        // For deadline alerts
  actionRequired: string        // The single next action to take
  createdAt: string
  dismissed: boolean
}
```

### Document Extraction (output of Claude parsers)

```typescript
interface WillExtraction {
  documentType: "will"
  executorName: string
  beneficiaries: { name: string; share?: string; specificBequest?: string }[]
  assets: { description: string; estimatedValue?: number }[]
  trustClauses: string[]
  specialInstructions: string[]
  codicils: string[]
  rawChunks: string[]           // For Redis vector embedding
}
```

---

## California Probate Rules Database

The DeadlineAgent compares estate state against these hardcoded rules (in `lib/rules/california-probate.ts`). This is the minimum viable ruleset for the hackathon:

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
| Debt payment order | Before any distribution | N/A — sequential | Paying out of order = personal liability |
| Property appraisal needed | Before DE-160 | Before 4-month deadline | Blocks inventory filing |

---

## Core AI Flows

### 1. Document Parse Flow

```
User uploads file (PDF / image)
  → formidable extracts file buffer
  → pdf-parse or sharp preprocesses
  → document-router.ts detects document type
  → correct parser prompt sent to Claude (vision + structured output)
  → Zod validates extraction JSON
  → Sentry transaction: { action: "document_parse", doc_type }
  → raw chunks embedded via OpenAI text-embedding-3-small
  → embeddings upserted to Redis Iris vector index
  → structured data merged into estate state in Redis KV
  → DeadlineAgent triggered to re-evaluate new state
  → alerts returned to UI
```

### 2. Chat RAG Flow

```
User sends message (text or Deepgram STT transcription)
  → embed query with text-embedding-3-small
  → Redis Iris vector search → top 5 relevant document chunks
  → load estate state JSON from Redis KV
  → build Claude system prompt:
      [base system prompt]
      [estate state JSON]
      [retrieved document chunks]
  → stream Claude response
  → if voice mode: pipe text to Deepgram TTS → stream audio
  → Sentry transaction: { action: "chat_query" }
```

### 3. DeadlineAgent Flow

```
Triggered by: Vercel cron (hourly) OR after every document parse
  → load estate state from Redis KV
  → run california-probate.ts rules against state
  → for each rule:
      calculate days_remaining (using date-fns)
      evaluate severity threshold
      check if alert already exists (deduplicate)
  → generate new alerts array ranked by severity
  → write updated alerts back to Redis KV
  → Sentry transaction: { action: "deadline_agent_run", rules_checked, alerts_fired }
  → return alerts to caller
```

### 4. Letter Generation Flow

```
User requests letter type (e.g. "Wells Fargo estate notification")
  → load estate state from Redis KV
  → select letter prompt from lib/prompts/letter-prompts.ts
  → inject estate-specific variables (deceased name, dates, account refs, case numbers)
  → Claude generates formatted letter
  → return draft to LetterPreview component for review
  → Sentry transaction: { action: "letter_generation", letter_type }
```

---

## System Prompt Template

The base system prompt injected into every Claude chat call (in `lib/prompts/system-prompt.ts`):

```
You are an estate administration assistant helping an executor manage the estate 
of {deceasedName}, who passed away on {dateOfDeath}. The executor is {executorName}.

This estate is in {state}. Letters testamentary were issued on {appointmentDate}, 
meaning the executor has had legal authority since that date.

ESTATE STATE:
{estateStateJSON}

RETRIEVED DOCUMENT CONTEXT:
{redisRetrievedChunks}

RULES YOU MUST FOLLOW:
- Answer using specific facts from the estate state and documents above, not generic probate advice
- When citing a deadline, always include the exact date and consequence of missing it
- When you don't have a fact (e.g. a missing account number), say so explicitly
- Never give legal advice. For questions requiring attorney judgment, say: 
  "This requires your attorney's input — it involves [reason]."
- Keep tone warm and direct. This person is grieving. Never be clinical.
- If stress or overwhelm is detectable, surface only the single most urgent next action.
- Always answer in plain English. Define any legal term you use.
```

---

## Demo Scenario (Hardcoded Seed Data)

For the hackathon demo, seed the following fictional estate to ensure a reliable, emotionally resonant presentation:

```typescript
const DEMO_ESTATE: EstateState = {
  id: "demo-milligan",
  deceasedName: "Robert A. Milligan",
  dateOfDeath: "2026-06-03",
  appointmentDate: "2026-06-10",
  state: "california",
  executor: { name: "Dana Milligan", email: "dana@demo.com" },
  assets: [
    { type: "real_estate", description: "1847 Marin Ave, Berkeley CA", estimatedValue: 220000, appraised: false },
    { type: "bank_account", description: "Wells Fargo checking ending 4412", value: 38240 },
    { type: "retirement", description: "Fidelity IRA ending 7731", value: 26500, beneficiaryNamed: true },
    { type: "vehicle", description: "2019 Honda Civic", estimatedValue: 12000, appraised: false }
  ],
  debts: [
    { creditor: "UCSF Medical Center", amount: 4200, type: "unsecured", notified: false },
    { creditor: "Chase Visa", amount: 3100, type: "unsecured", notified: false },
    { creditor: "First Republic Mortgage", amount: 141000, type: "secured", notified: false }
  ],
  beneficiaries: [
    { name: "Dana Milligan", share: "40%" },
    { name: "Sarah Milligan", share: "40%" },
    { name: "Marcus Milligan", share: "20%" }
  ],
  phase: 2,
  // appointmentDate was June 10 → DE-160 due October 10 → ~9 days from demo date
}
```

This seed data is designed to trigger two critical DeadlineAgent alerts live during the demo:
1. DE-160 filing due in ~9 days, no property appraisal uploaded
2. Creditors not yet notified — 30-day window from appointment date nearly elapsed

---

## Hackathon Build Order

| Hours | What to build | Why first |
|-------|--------------|-----------|
| 0–2 | Claude document extraction (hardcoded text input) | Foundation everything else runs on |
| 2–5 | Redis Iris vector store + KV estate state | Enables RAG and DeadlineAgent |
| 5–9 | Estate-aware chat with RAG | First demo-worthy moment |
| 9–14 | DeadlineAgent rules engine | The actual product moat |
| 14–17 | Deepgram voice (STT + TTS) | Emotional demo hook, wins track |
| 17–18 | Sentry instrumentation | 30 min, wins Nintendo Switches |
| 18–22 | Letter generation + dashboard UI | Visual polish, completes story |
| 22–48 | File upload, edge cases, demo prep, sleep | Ship something that works reliably |

---

## What NOT to Build at the Hackathon

These are real product ideas that belong in the post-hackathon roadmap. Do not start them during the 48-hour window:

- **Browserbase / web automation** — Cool but emotionally disconnected from core pain
- **Band multi-agent coordination** — Architectural complexity judges won't reward in a demo
- **Orkes / Agentspan workflow engine** — Overkill; phase logic can live in Claude's context
- **Court e-filing automation** — Legally sensitive, state-specific, months of work
- **Beneficiary portal** — Real product need, wrong time
- **Arize + Terac evals** — Real value, wrong time; needs dedicated team member

---

## Package.json Dependencies

```json
{
  "dependencies": {
    "@anthropic-ai/sdk": "^0.27.0",
    "@deepgram/sdk": "^3.5.0",
    "@sentry/nextjs": "^8.0.0",
    "@upstash/redis": "^1.34.0",
    "@upstash/vector": "^1.1.5",
    "ai": "^3.3.0",
    "date-fns": "^3.6.0",
    "formidable": "^3.5.1",
    "ioredis": "^5.4.1",
    "nanoid": "^5.0.7",
    "next": "14.2.5",
    "openai": "^4.55.0",
    "pdf-parse": "^1.1.1",
    "react": "^18",
    "react-dom": "^18",
    "sharp": "^0.33.4",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/formidable": "^3.4.5",
    "@types/node": "^20",
    "@types/pdf-parse": "^1.1.4",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10.0.1",
    "eslint": "^8",
    "eslint-config-next": "14.2.5",
    "postcss": "^8",
    "tailwindcss": "^3.4.1",
    "typescript": "^5"
  }
}
```

---

## Sponsor Track Requirements

| Sponsor | Prize | What must be true at demo |
|---------|-------|--------------------------|
| Anthropic | $5k API credits + office hours | Built with Claude Code; Claude doing hard reasoning on a meaningful human problem |
| Deepgram | Nintendo Switch 2 per member | At least one Deepgram product (STT, TTS, or voice agent) demonstrably essential to experience |
| Redis | Mac Minis + 25k cloud credits | Redis Iris used for vector search / agent memory; not just caching |
| Sentry | Nintendo Switch 2 per member | Sentry used for observability; bonus points explicitly stated in criteria |

---

## Positioning

**Before ClearPath:** Dana spends 180 hours, makes three costly mistakes, pays $4,200 in unexpected fees, and nobody ever told her the rules that would have prevented all of it.

**After ClearPath:** Dana uploads three documents. The AI reconstructs her estate. The AI tells her the next three actions. The AI catches the mistake before it happens.

That is the complete story. Every architectural decision should serve that story. Nothing that doesn't serve that story gets built at the hackathon.
