# Member 2 — Data Layer

**Owner**: TBD  
**Track dependency**: The shared foundation. Build Redis client and Zod schemas in the first hour so everyone else can import and use them.

---

## Your Mission

You own all data infrastructure: Redis (KV + vector), Zod schemas, TypeScript types, and the demo seed data. Every other team member writes to or reads from the estate state you define. Build the contracts first (types + schemas), then implement the Redis utilities that wrap them.

---

## Files You Own

```
lib/
├── redis.ts                     ← Redis client + all KV and vector helpers
└── schemas/
    ├── estate-state.ts          ← Zod schema for EstateState (the central object)
    ├── document-extractions.ts  ← Zod schemas per document type (will, bank, deed)
    └── alerts.ts                ← Zod schema for Alert objects

types/
├── estate.ts                    ← TS types: EstateState, Asset, Debt, Beneficiary, Task
├── alerts.ts                    ← TS types: Alert, AlertSeverity, AlertType
└── documents.ts                 ← TS types: DocumentType union, WillExtraction, etc.

lib/
└── seed/
    └── demo-estate.ts           ← DEMO_ESTATE seed object + seedDemoEstate() function
```

---

## Build Order

### Phase 1 — TypeScript Types (Hour 0–1)
Write these first. Everyone imports from `types/`. Do not export Zod schemas from here — keep types and schemas separate.

```typescript
// types/estate.ts
export type EstatePhase = 1 | 2 | 3 | 4 | 5 | 6

export interface Asset {
  id: string
  type: "real_estate" | "bank_account" | "retirement" | "vehicle" | "personal_property" | "other"
  description: string
  estimatedValue?: number
  appraised: boolean
  appraisedValue?: number
  beneficiaryNamed?: boolean   // For retirement accounts — bypasses probate
}

export interface Debt {
  id: string
  creditor: string
  amount: number
  type: "secured" | "unsecured" | "priority"
  notified: boolean
  notifiedDate?: string
  claimFiled?: boolean
}

export interface Beneficiary {
  id: string
  name: string
  share?: string               // "40%" or fractional
  specificBequest?: string     // "the 1968 Mustang"
  contactInfo?: string
}

export interface UploadedDocument {
  id: string
  filename: string
  documentType: DocumentType
  uploadedAt: string
  extractionId: string         // Key to the extraction result
}

export interface Task {
  id: string
  title: string
  description: string
  phase: EstatePhase
  completed: boolean
  completedAt?: string
  dueDate?: string
  ruleId?: string              // Links to california-probate.ts rule
}

export interface EstateState {
  id: string
  deceasedName: string
  dateOfDeath: string
  appointmentDate: string
  state: "california"
  executor: { name: string; email: string }
  assets: Asset[]
  debts: Debt[]
  beneficiaries: Beneficiary[]
  documents: UploadedDocument[]
  tasks: Task[]
  alerts: Alert[]
  phase: EstatePhase
  createdAt: string
  updatedAt: string
}
```

```typescript
// types/alerts.ts
export type AlertSeverity = "critical" | "warning" | "info"
export type AlertType = "deadline" | "liability" | "missing_doc" | "rule_violation"

export interface Alert {
  id: string
  severity: AlertSeverity
  type: AlertType
  title: string
  body: string
  rule: string
  daysRemaining?: number
  actionRequired: string
  createdAt: string
  dismissed: boolean
}
```

```typescript
// types/documents.ts
export type DocumentType = "will" | "bank_statement" | "deed" | "insurance" | "unknown"

export interface WillExtraction {
  documentType: "will"
  executorName: string
  beneficiaries: { name: string; share?: string; specificBequest?: string }[]
  assets: { description: string; estimatedValue?: number }[]
  trustClauses: string[]
  specialInstructions: string[]
  codicils: string[]
  rawChunks: string[]
}

export interface BankStatementExtraction {
  documentType: "bank_statement"
  institutionName: string
  accountLast4: string
  accountType: string
  balance: number
  statementDate: string
  transactions: { date: string; description: string; amount: number }[]
  rawChunks: string[]
}

export interface DeedExtraction {
  documentType: "deed"
  propertyAddress: string
  apn: string
  legalDescription: string
  grantorName: string
  granteeName: string
  recordedDate: string
  estimatedValue?: number
  rawChunks: string[]
}

export type DocumentExtraction = WillExtraction | BankStatementExtraction | DeedExtraction
```

### Phase 2 — Zod Schemas (Hour 1)
Mirror the TypeScript interfaces with Zod for runtime validation of Claude's output. Member 1 imports these.

```typescript
// lib/schemas/document-extractions.ts
import { z } from "zod"

export const WillExtractionSchema = z.object({
  documentType: z.literal("will"),
  executorName: z.string(),
  beneficiaries: z.array(z.object({
    name: z.string(),
    share: z.string().optional(),
    specificBequest: z.string().optional(),
  })),
  assets: z.array(z.object({
    description: z.string(),
    estimatedValue: z.number().optional(),
  })),
  trustClauses: z.array(z.string()),
  specialInstructions: z.array(z.string()),
  codicils: z.array(z.string()),
  rawChunks: z.array(z.string()),
})

export const BankStatementExtractionSchema = z.object({ /* ... */ })
export const DeedExtractionSchema = z.object({ /* ... */ })
```

```typescript
// lib/schemas/alerts.ts
export const AlertSchema = z.object({
  id: z.string(),
  severity: z.enum(["critical", "warning", "info"]),
  type: z.enum(["deadline", "liability", "missing_doc", "rule_violation"]),
  title: z.string(),
  body: z.string(),
  rule: z.string(),
  daysRemaining: z.number().optional(),
  actionRequired: z.string(),
  createdAt: z.string(),
  dismissed: z.boolean(),
})
```

```typescript
// lib/schemas/estate-state.ts
export const EstateStateSchema = z.object({
  id: z.string(),
  deceasedName: z.string(),
  dateOfDeath: z.string(),
  appointmentDate: z.string(),
  state: z.literal("california"),
  executor: z.object({ name: z.string(), email: z.string() }),
  assets: z.array(AssetSchema),
  debts: z.array(DebtSchema),
  beneficiaries: z.array(BeneficiarySchema),
  documents: z.array(UploadedDocumentSchema),
  tasks: z.array(TaskSchema),
  alerts: z.array(AlertSchema),
  phase: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4), z.literal(5), z.literal(6)]),
  createdAt: z.string(),
  updatedAt: z.string(),
})
```

### Phase 3 — Redis Client (Hour 1–3)
`lib/redis.ts` — export a singleton client plus all the utility functions others call.

```typescript
import { Redis } from "@upstash/redis"
import { Index } from "@upstash/vector"
import type { EstateState } from "../types/estate"

// Clients
export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
})

export const vectorIndex = new Index({
  url: process.env.UPSTASH_VECTOR_REST_URL!,
  token: process.env.UPSTASH_VECTOR_REST_TOKEN!,
})

// KV helpers
export const ESTATE_KEY = (id: string) => `estate:${id}`

export async function getEstateState(estateId: string): Promise<EstateState | null> {
  const data = await redis.get<EstateState>(ESTATE_KEY(estateId))
  return data
}

export async function setEstateState(state: EstateState): Promise<void> {
  await redis.set(ESTATE_KEY(state.id), { ...state, updatedAt: new Date().toISOString() })
}

// Merge extraction data into estate state — called by Member 1's parse-document route
export async function mergeEstateState(estateId: string, updates: Partial<EstateState>): Promise<EstateState> {
  const current = await getEstateState(estateId) ?? createBlankEstate(estateId)
  const merged = deepMerge(current, updates)
  await setEstateState(merged)
  return merged
}

// Vector helpers — called by Member 1's embeddings flow
export async function upsertVectors(
  estateId: string,
  chunks: string[],
  embeddings: number[][]
): Promise<void> {
  const vectors = embeddings.map((vector, i) => ({
    id: `${estateId}-chunk-${Date.now()}-${i}`,
    vector,
    metadata: { estateId, chunkIndex: i, text: chunks[i] },
  }))
  await vectorIndex.upsert(vectors)
}

// Semantic search — called by Member 4's chat route
export async function searchVectors(
  estateId: string,
  queryEmbedding: number[],
  topK = 5
): Promise<string[]> {
  const results = await vectorIndex.query({
    vector: queryEmbedding,
    topK,
    includeMetadata: true,
    filter: `estateId = '${estateId}'`,
  })
  return results.map(r => r.metadata?.text as string).filter(Boolean)
}

// Alert helpers — called by Member 3's DeadlineAgent
export async function writeAlerts(estateId: string, alerts: Alert[]): Promise<void> {
  await redis.set(`alerts:${estateId}`, alerts)
}

export async function getAlerts(estateId: string): Promise<Alert[]> {
  return await redis.get<Alert[]>(`alerts:${estateId}`) ?? []
}
```

### Phase 4 — Demo Seed Data (Hour 3)
This must be loadable at any time to reset the demo to a known good state.

```typescript
// lib/seed/demo-estate.ts
import { nanoid } from "nanoid"
import { setEstateState } from "../redis"
import type { EstateState } from "../../types/estate"

export const DEMO_ESTATE: EstateState = {
  id: "demo-milligan",
  deceasedName: "Robert A. Milligan",
  dateOfDeath: "2026-06-03",
  appointmentDate: "2026-06-10",
  state: "california",
  executor: { name: "Dana Milligan", email: "dana@demo.com" },
  assets: [
    { id: nanoid(), type: "real_estate", description: "1847 Marin Ave, Berkeley CA", estimatedValue: 220000, appraised: false },
    { id: nanoid(), type: "bank_account", description: "Wells Fargo checking ending 4412", estimatedValue: 38240, appraised: false },
    { id: nanoid(), type: "retirement", description: "Fidelity IRA ending 7731", estimatedValue: 26500, appraised: false, beneficiaryNamed: true },
    { id: nanoid(), type: "vehicle", description: "2019 Honda Civic", estimatedValue: 12000, appraised: false },
  ],
  debts: [
    { id: nanoid(), creditor: "UCSF Medical Center", amount: 4200, type: "unsecured", notified: false },
    { id: nanoid(), creditor: "Chase Visa", amount: 3100, type: "unsecured", notified: false },
    { id: nanoid(), creditor: "First Republic Mortgage", amount: 141000, type: "secured", notified: false },
  ],
  beneficiaries: [
    { id: nanoid(), name: "Dana Milligan", share: "40%" },
    { id: nanoid(), name: "Sarah Milligan", share: "40%" },
    { id: nanoid(), name: "Marcus Milligan", share: "20%" },
  ],
  documents: [],
  tasks: [],
  alerts: [],
  phase: 2,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

export async function seedDemoEstate(): Promise<void> {
  await setEstateState(DEMO_ESTATE)
  console.log("Demo estate seeded:", DEMO_ESTATE.id)
}
```

Also create `app/api/seed/route.ts` — a GET endpoint that calls `seedDemoEstate()` for easy demo resets.

---

## Coordination Points

| You need from... | What |
|-----------------|------|
| Nobody — you build first | Types and schemas must be ready in hour 1 |

| Others need from you | What |
|--------------------|------|
| **Member 1** | `WillExtractionSchema`, `BankStatementExtractionSchema`, `DeedExtractionSchema` from `lib/schemas/` |
| **Member 1** | `upsertVectors()` and `mergeEstateState()` from `lib/redis.ts` |
| **Member 3** | `getEstateState()`, `writeAlerts()`, `getAlerts()` from `lib/redis.ts` |
| **Member 4** | `getEstateState()`, `searchVectors()` from `lib/redis.ts` |
| **Everyone** | All types from `types/` |

---

## Acceptance Criteria

- [ ] `types/estate.ts`, `types/alerts.ts`, `types/documents.ts` — all exported, no compile errors
- [ ] `lib/schemas/` — Zod schemas for EstateState, all document extractions, Alert
- [ ] `lib/redis.ts` exports: `redis`, `vectorIndex`, `getEstateState`, `setEstateState`, `mergeEstateState`, `upsertVectors`, `searchVectors`, `writeAlerts`, `getAlerts`
- [ ] `seedDemoEstate()` writes DEMO_ESTATE to Redis and returns without error
- [ ] `GET /api/seed` resets demo estate successfully
- [ ] Redis KV and vector index both connect (test with seed + read-back)

---

## Sponsor Requirements You Unlock

- **Redis track**: Your `lib/redis.ts` is the direct interface to Redis Iris (vector) and KV. Make sure vector search has a `filter` on `estateId` — demonstrate that Redis is doing meaningful agent memory, not just caching.
- Make `searchVectors` return both text and metadata (score, source doc) so Member 4 can surface citations in the chat UI.
