# ClearPath Estate — Claude Instructions

## What This Is
AI executor assistant. Parses estate documents into a live state graph, then proactively alerts the executor before probate deadlines and liability triggers are missed. Built with Claude Code for a 24-hour hackathon.

Full project detail: [project_overview.md](project_overview.md)

---

## Stack (Quick Reference)
- **Framework**: Next.js 14 App Router, TypeScript, Tailwind CSS
- **AI**: Claude `claude-sonnet-4-6` (Anthropic SDK) — reasoning, parsing, chat, letters
- **Embeddings**: OpenAI `text-embedding-3-small`
- **Vector + KV**: Upstash Redis (vector index for RAG, KV for estate state)
- **Voice**: Deepgram STT + TTS
- **Observability**: Sentry (`@sentry/nextjs`) — wrap every Claude call and agent run
- **Validation**: Zod for all Claude structured outputs and API schemas
- **Dates**: date-fns for all deadline arithmetic
- **Uploads**: formidable + pdf-parse + sharp

---

## Key File Locations

| Purpose | Path |
|---------|------|
| Anthropic client | `lib/claude.ts` |
| Redis client (KV + vector) | `lib/redis.ts` |
| OpenAI embeddings | `lib/embeddings.ts` |
| Deepgram client | `lib/deepgram.ts` |
| Sentry wrappers | `lib/sentry.ts` |
| Document parsers | `lib/parsers/` |
| DeadlineAgent | `lib/agents/deadline-agent.ts` |
| CA probate rules | `lib/rules/california-probate.ts` |
| Prompts | `lib/prompts/` |
| Zod schemas | `lib/schemas/` |
| TypeScript types | `types/` |
| API routes | `app/api/` |
| UI components | `components/` |

---

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/parse-document` | POST | File upload → Claude extract → Redis store |
| `/api/chat` | POST | Message → RAG → Claude stream |
| `/api/voice/transcribe` | POST | Audio → Deepgram STT → text |
| `/api/voice/speak` | POST | Text → Deepgram TTS → audio |
| `/api/deadline-agent` | GET | Run rules engine → return alerts |
| `/api/generate-letter` | POST | Letter type → Claude draft |
| `/api/cron/deadline-check` | GET | Vercel cron trigger for DeadlineAgent |

---

## Core Data Shapes

```typescript
// Estate state — Redis KV key: estate:{id}
interface EstateState {
  id: string
  deceasedName: string
  dateOfDeath: string          // ISO date
  appointmentDate: string      // Date letters testamentary issued
  state: "california"
  executor: { name: string; email: string }
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

// Alert — output of DeadlineAgent
interface Alert {
  id: string
  severity: "critical" | "warning" | "info"
  type: "deadline" | "liability" | "missing_doc" | "rule_violation"
  title: string
  body: string
  rule: string
  daysRemaining?: number
  actionRequired: string
  createdAt: string
  dismissed: boolean
}
```

---

## Environment Variables

```bash
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
UPSTASH_VECTOR_REST_URL=
UPSTASH_VECTOR_REST_TOKEN=
DEEPGRAM_API_KEY=
SENTRY_DSN=
NEXT_PUBLIC_SENTRY_DSN=
SENTRY_ORG=
SENTRY_PROJECT=
NEXT_PUBLIC_APP_URL=http://localhost:3000
CRON_SECRET=
```

---

## Demo Estate (Seed Data)

Estate ID: `demo-milligan` | Deceased: Robert A. Milligan | Date of death: 2026-06-03 | Appointment: 2026-06-10 | Executor: Dana Milligan

Designed to trigger live during demo:
1. **CRITICAL**: DE-160 Inventory & Appraisal due ~9 days out (Oct 10), no appraisal uploaded
2. **CRITICAL**: Creditors not notified — 30-day window from June 10 nearly elapsed

Full seed object in [project_overview.md](project_overview.md#demo-scenario-hardcoded-seed-data).

---

## Critical Rules
- **Never commit `.env.local`**
- Every Claude call must be wrapped in a Sentry transaction with tags: `estate_id`, `action_type`
- Zod-validate all Claude structured outputs before writing to Redis
- CA probate jurisdiction only — hardcoded for hackathon
- Debt payment order: secured → unsecured → distributions. Out-of-order = executor personal liability
- Never give legal advice in the chat prompt. Use: *"This requires your attorney's input — it involves [reason]."*
- Tone: warm and direct. Never clinical. This person is grieving.

---

## Team Division
- **Member 1 (Alex)** — Document Intelligence: Claude parsers, embeddings, parse-document API → [team/member1-document-intelligence.md](team/member1-document-intelligence.md)
- **Member 2** — Data Layer: Redis setup, Zod schemas, TypeScript types, estate state, seed data → [team/member2-data-layer.md](team/member2-data-layer.md)
- **Member 3** — DeadlineAgent + Letters: Rules engine, alerts, letter generation, Sentry, cron → [team/member3-deadline-agent.md](team/member3-deadline-agent.md)
- **Member 4** — Frontend + Chat + Voice: All UI, RAG chat API, system prompt, Deepgram → [team/member4-frontend-chat-voice.md](team/member4-frontend-chat-voice.md)
