# Member 3 — DeadlineAgent + Letters + Observability

**Owner**: TBD  
**Track dependency**: DeadlineAgent is the product moat — the thing that makes ClearPath different from a chatbot. Your alerts are the hero of the demo. Sentry wraps unlock the Nintendo Switch prize.

---

## Your Mission

You own the proactive intelligence layer. The DeadlineAgent reads the current estate state, compares it against hardcoded California probate rules, and fires ranked alerts before the executor makes an expensive mistake. You also own letter generation (Claude drafts legal letters ready to sign) and Sentry instrumentation (wraps all Claude calls and agent runs in observable transactions).

---

## Files You Own

```
lib/
├── sentry.ts                        ← Sentry client + withSentryTransaction() wrapper
├── rules/
│   └── california-probate.ts        ← Hardcoded CA probate rules (11 rules minimum)
├── agents/
│   └── deadline-agent.ts            ← Rules engine: estate state → alerts array
└── prompts/
    ├── letter-prompts.ts            ← Letter generation prompts (5+ letter types)
    └── system-prompt.ts             ← Base chat system prompt (shared with Member 4)

app/api/
├── deadline-agent/
│   └── route.ts                     ← GET: run agent → return fresh alerts
├── generate-letter/
│   └── route.ts                     ← POST: letter type + estate state → Claude draft
└── cron/
    └── deadline-check/
        └── route.ts                 ← Vercel cron trigger (hourly)
```

---

## Build Order

### Phase 1 — Sentry Setup (Hour 0–1, ~30 min)
Do this first. It's 30 minutes of work and wins Nintendo Switches. Every team member's Claude calls go through your wrapper.

```typescript
// lib/sentry.ts
import * as Sentry from "@sentry/nextjs"

export function withSentryTransaction<T>(
  name: string,
  tags: Record<string, string>,
  fn: () => Promise<T>
): Promise<T> {
  return Sentry.startSpan(
    { name, attributes: tags },
    fn
  )
}

// Usage by any team member:
// await withSentryTransaction("document_parse", { estate_id: "demo-milligan", action_type: "document_parse", doc_type: "will" }, async () => {
//   return await extractStructured(...)
// })
```

Also initialize Sentry in `next.config.ts` / `sentry.client.config.ts` — follow `@sentry/nextjs` setup docs.

Required Sentry tags across all transactions:
- `estate_id` — always the estate being worked on
- `action_type` — one of: `document_parse`, `chat_query`, `deadline_agent_run`, `letter_generation`
- `agent_name` — `"deadline_agent"` when running the rules engine
- `doc_type` — when parsing documents
- `rule_checked` — when evaluating a specific probate rule
- `alerts_fired` — count of new alerts generated

### Phase 2 — California Probate Rules (Hour 1–3)
Write `lib/rules/california-probate.ts`. This is a data file — a typed array of rule objects the DeadlineAgent iterates over.

```typescript
// lib/rules/california-probate.ts
import type { EstateState } from "../../types/estate"
import type { Alert } from "../../types/alerts"

export interface ProbateRule {
  id: string
  title: string
  statute: string           // "CA Probate Code §9052"
  deadlineDays?: number     // Days from trigger date. null = ASAP
  triggerField: keyof EstateState | "appointmentDate" | "dateOfDeath"
  evaluate: (state: EstateState, today: Date) => Alert | null
}

export const CALIFORNIA_PROBATE_RULES: ProbateRule[] = [
  {
    id: "DE-160",
    title: "Inventory & Appraisal",
    statute: "CA Probate Code §8800",
    deadlineDays: 120,           // 4 months from letters testamentary
    triggerField: "appointmentDate",
    evaluate: (state, today) => {
      const due = addDays(parseISO(state.appointmentDate), 120)
      const daysRemaining = differenceInDays(due, today)
      const allAppraised = state.assets
        .filter(a => a.type === "real_estate" || a.type === "vehicle")
        .every(a => a.appraised)

      if (allAppraised) return null  // Rule satisfied

      if (daysRemaining <= 14) {
        return {
          id: `DE-160-${state.id}`,
          severity: daysRemaining <= 7 ? "critical" : "warning",
          type: "deadline",
          title: `DE-160 Inventory & Appraisal due in ${daysRemaining} days`,
          body: `You must file a complete inventory of all estate assets with the probate court by ${format(due, "MMMM d, yyyy")}. Missing this deadline triggers court sanctions and makes you personally liable for any losses.`,
          rule: "CA Probate Code §8800",
          daysRemaining,
          actionRequired: "Order property appraisals immediately, then complete and file DE-160 with the court.",
          createdAt: new Date().toISOString(),
          dismissed: false,
        }
      }
      return null
    }
  },
  {
    id: "creditor-notification",
    title: "Creditor Notification (Certified Mail)",
    statute: "CA Probate Code §9051",
    deadlineDays: 30,
    triggerField: "appointmentDate",
    evaluate: (state, today) => {
      const anyUnnotified = state.debts.some(d => !d.notified)
      if (!anyUnnotified) return null

      const due = addDays(parseISO(state.appointmentDate), 30)
      const daysRemaining = differenceInDays(due, today)

      if (daysRemaining <= 30) {
        return {
          id: `creditor-notification-${state.id}`,
          severity: daysRemaining <= 5 ? "critical" : "warning",
          type: "liability",
          title: `Creditor notification required — ${daysRemaining} days remaining`,
          body: `You must notify all known creditors by certified mail within 30 days of receiving letters testamentary. Failing to notify creditors and then distributing assets makes you personally liable for those debts.`,
          rule: "CA Probate Code §9051",
          daysRemaining,
          actionRequired: "Send certified mail notices to all creditors: UCSF Medical Center, Chase Visa, First Republic Mortgage.",
          createdAt: new Date().toISOString(),
          dismissed: false,
        }
      }
      return null
    }
  },
  // Add remaining 9 rules from project_overview.md:
  // DE-140 petition, death certificates, newspaper notice, creditor claim period,
  // estate EIN, final 1040, Form 1041, debt payment order, property appraisal needed
]
```

### Phase 3 — DeadlineAgent (Hour 3–5)

```typescript
// lib/agents/deadline-agent.ts
import { differenceInDays, addDays, parseISO } from "date-fns"
import { CALIFORNIA_PROBATE_RULES } from "../rules/california-probate"
import { getEstateState, writeAlerts, getAlerts } from "../redis"
import { withSentryTransaction } from "../sentry"
import type { Alert } from "../../types/alerts"

export async function runDeadlineAgent(estateId: string): Promise<Alert[]> {
  return withSentryTransaction(
    "deadline_agent_run",
    { estate_id: estateId, action_type: "deadline_agent_run", agent_name: "deadline_agent" },
    async () => {
      const state = await getEstateState(estateId)
      if (!state) throw new Error(`Estate not found: ${estateId}`)

      const today = new Date()
      const existingAlerts = await getAlerts(estateId)
      const existingIds = new Set(existingAlerts.map(a => a.id))

      const newAlerts: Alert[] = []
      let rulesChecked = 0

      for (const rule of CALIFORNIA_PROBATE_RULES) {
        rulesChecked++
        const alert = rule.evaluate(state, today)

        if (alert && !existingIds.has(alert.id)) {
          newAlerts.push(alert)
        }
      }

      // Merge with existing non-dismissed alerts, re-rank by severity
      const allAlerts = [
        ...existingAlerts.filter(a => !a.dismissed),
        ...newAlerts,
      ].sort((a, b) => {
        const rank = { critical: 0, warning: 1, info: 2 }
        return rank[a.severity] - rank[b.severity]
      })

      await writeAlerts(estateId, allAlerts)

      // Add Sentry attributes for rules_checked and alerts_fired
      return allAlerts
    }
  )
}
```

### Phase 4 — Letter Generation (Hour 5–7)

```typescript
// lib/prompts/letter-prompts.ts
export type LetterType =
  | "creditor_notice"
  | "bank_notification"
  | "irs_ein_request"
  | "beneficiary_update"
  | "property_transfer"

export const LETTER_PROMPTS: Record<LetterType, (state: EstateState) => string> = {
  creditor_notice: (state) => `
Draft a formal creditor notification letter for the estate of ${state.deceasedName}.
Use these details:
- Executor: ${state.executor.name}
- Date of Death: ${state.dateOfDeath}
- Letters Testamentary Issued: ${state.appointmentDate}

The letter must:
1. State the creditor's name and known claim amount
2. Cite CA Probate Code §9051 notification requirements
3. State the 60-day claim filing window from date of this notice
4. Include executor contact information
5. Request that claims be submitted in writing

Format as a formal business letter. Use [CREDITOR NAME] and [CLAIM AMOUNT] as placeholders.
`,
  bank_notification: (state) => `...`,
  irs_ein_request: (state) => `...`,
  beneficiary_update: (state) => `...`,
  property_transfer: (state) => `...`,
}
```

```typescript
// app/api/generate-letter/route.ts
import { NextRequest, NextResponse } from "next/server"
import { getEstateState } from "@/lib/redis"
import { anthropic } from "@/lib/claude"
import { LETTER_PROMPTS, LetterType } from "@/lib/prompts/letter-prompts"
import { withSentryTransaction } from "@/lib/sentry"

export async function POST(req: NextRequest) {
  const { estateId, letterType } = await req.json()

  const draft = await withSentryTransaction(
    "letter_generation",
    { estate_id: estateId, action_type: "letter_generation", letter_type: letterType },
    async () => {
      const state = await getEstateState(estateId)
      if (!state) throw new Error("Estate not found")

      const prompt = LETTER_PROMPTS[letterType as LetterType](state)
      const response = await anthropic.messages.create({
        model: "claude-sonnet-4-6",
        max_tokens: 2048,
        messages: [{ role: "user", content: prompt }],
      })
      return response.content[0].type === "text" ? response.content[0].text : ""
    }
  )

  return NextResponse.json({ draft })
}
```

### Phase 5 — System Prompt (Hour 6)
Write `lib/prompts/system-prompt.ts` — shared with Member 4 who calls it in the chat API.

```typescript
// lib/prompts/system-prompt.ts
import type { EstateState } from "../../types/estate"

export function buildSystemPrompt(state: EstateState, retrievedChunks: string[]): string {
  return `You are an estate administration assistant helping an executor manage the estate of ${state.deceasedName}, who passed away on ${state.dateOfDeath}. The executor is ${state.executor.name}.

This estate is in California. Letters testamentary were issued on ${state.appointmentDate}, meaning the executor has had legal authority since that date.

ESTATE STATE:
${JSON.stringify(state, null, 2)}

RETRIEVED DOCUMENT CONTEXT:
${retrievedChunks.join("\n\n---\n\n")}

RULES YOU MUST FOLLOW:
- Answer using specific facts from the estate state and documents above, not generic probate advice
- When citing a deadline, always include the exact date and consequence of missing it
- When you don't have a fact (e.g. a missing account number), say so explicitly
- Never give legal advice. For questions requiring attorney judgment, say: "This requires your attorney's input — it involves [reason]."
- Keep tone warm and direct. This person is grieving. Never be clinical.
- If stress or overwhelm is detectable, surface only the single most urgent next action.
- Always answer in plain English. Define any legal term you use.`
}
```

### Phase 6 — API Routes + Cron (Hour 7)

```typescript
// app/api/deadline-agent/route.ts
export async function GET(req: NextRequest) {
  const estateId = req.nextUrl.searchParams.get("estateId") ?? "demo-milligan"
  const alerts = await runDeadlineAgent(estateId)
  return NextResponse.json({ alerts })
}

// app/api/cron/deadline-check/route.ts
export async function GET(req: NextRequest) {
  // Validate Vercel cron secret
  if (req.headers.get("authorization") !== `Bearer ${process.env.CRON_SECRET}`) {
    return new Response("Unauthorized", { status: 401 })
  }
  const alerts = await runDeadlineAgent("demo-milligan")
  return NextResponse.json({ ran: true, alertCount: alerts.length })
}
```

Add to `vercel.json`:
```json
{
  "crons": [{
    "path": "/api/cron/deadline-check",
    "schedule": "0 * * * *"
  }]
}
```

---

## Coordination Points

| You need from... | What |
|-----------------|------|
| **Member 2** | `getEstateState`, `writeAlerts`, `getAlerts` from `lib/redis.ts` |
| **Member 2** | `EstateState`, `Alert` types from `types/` |
| **Member 1** | `anthropic` client from `lib/claude.ts` (for letter generation) |

| Others need from you | What |
|--------------------|------|
| **Member 1** | `withSentryTransaction()` from `lib/sentry.ts` — wrap document parse calls |
| **Member 4** | `buildSystemPrompt()` from `lib/prompts/system-prompt.ts` |
| **Member 4** | `runDeadlineAgent()` — called after chat to refresh alerts |
| **Member 4** | `GET /api/deadline-agent` endpoint — polled by dashboard |
| **Member 4** | `POST /api/generate-letter` endpoint — called by LetterPreview component |

---

## The 11 Required Rules

Implement all of these in `california-probate.ts`:

| Rule ID | Trigger | Window | Severity threshold |
|---------|---------|--------|--------------------|
| `DE-140` | dateOfDeath | File ASAP | warning always |
| `death-certificates` | dateOfDeath | ASAP | warning always |
| `DE-160` | appointmentDate | 120 days | critical ≤7d, warning ≤14d |
| `creditor-notification` | appointmentDate | 30 days | critical ≤5d, warning ≤30d |
| `newspaper-notice` | appointmentDate | 21 days | warning if not done |
| `creditor-claim-period` | appointmentDate | 120 days | info until distribution |
| `estate-ein` | assets has bank_account | ASAP | critical if no EIN |
| `final-1040` | dateOfDeath | April 15 next year | warning within 90d |
| `form-1041` | estate earns income | April 15 next year | warning within 90d |
| `debt-payment-order` | before any distribution | N/A | critical if wrong order |
| `property-appraisal` | appointmentDate | Before DE-160 | critical if appraised:false |

---

## Acceptance Criteria

- [ ] `lib/sentry.ts` exports `withSentryTransaction()` — works for all team members
- [ ] Sentry initialized in Next.js (client + server configs)
- [ ] All 11 CA probate rules implemented in `california-probate.ts`
- [ ] `runDeadlineAgent("demo-milligan")` returns 2 critical alerts on fresh seed data
- [ ] `GET /api/deadline-agent?estateId=demo-milligan` returns alerts JSON
- [ ] `POST /api/generate-letter` returns a formatted creditor notice letter
- [ ] `buildSystemPrompt()` exported from `lib/prompts/system-prompt.ts`
- [ ] Vercel cron configured in `vercel.json`

---

## Sponsor Requirements You Unlock

- **Sentry track**: Every team member's Claude call must go through your `withSentryTransaction`. The demo must show a Sentry dashboard with visible transactions tagged with `estate_id`, `action_type`, and `alerts_fired`. This is a 30-minute setup that wins a Nintendo Switch per team member — make sure it's working.
- **Anthropic track**: DeadlineAgent is Claude doing proactive hard reasoning, not question-answering. It's the core demo moment.
