# Member 1 — Document Intelligence

**Owner**: Alex  
**Track dependency**: Everything else depends on a working estate state object. Build and unblock others first.

---

## Your Mission

You own the pipeline that turns raw uploaded files into structured estate data. A will, bank statement, or deed gets uploaded — you make Claude read it and write structured JSON to Redis. Without this, there is no estate state, no DeadlineAgent alerts, and no RAG chat. Ship the parser first.

---

## Files You Own

```
lib/
├── claude.ts                    ← Anthropic client singleton + helper wrappers
├── embeddings.ts                ← OpenAI text-embedding-3-small calls
├── parsers/
│   ├── document-router.ts       ← Detect doc type → dispatch to correct parser
│   ├── will-parser.ts           ← Will extraction prompt + Zod validation
│   ├── bank-statement-parser.ts ← Bank statement extraction
│   └── deed-parser.ts           ← Property deed extraction
└── prompts/
    └── extraction-prompts.ts    ← All per-doc-type prompts (lives here, not in parsers)

app/api/
└── parse-document/
    └── route.ts                 ← POST endpoint: receive file → parse → write to Redis → trigger DeadlineAgent
```

---

## Build Order

### Phase 1 — Claude Client (Hour 0–1)
Build `lib/claude.ts` first. Everything calls this.

```typescript
import Anthropic from "@anthropic-ai/sdk"

export const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY })

// Structured extraction — use this for all document parsing
export async function extractStructured<T>(
  prompt: string,
  content: string | { type: "image"; data: string; mediaType: string },
  schema: z.ZodType<T>
): Promise<T> {
  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-6",
    max_tokens: 4096,
    messages: [{ role: "user", content: [
      typeof content === "string"
        ? { type: "text", text: content }
        : { type: "image", source: { type: "base64", ...content } },
      { type: "text", text: prompt }
    ]}],
  })
  // Parse JSON from response, validate with schema
}

// Streaming chat — used by Member 4
export function streamChat(messages: MessageParam[], systemPrompt: string) {
  return anthropic.messages.stream({ model: "claude-sonnet-4-6", max_tokens: 2048, system: systemPrompt, messages })
}
```

### Phase 2 — Extraction Prompts (Hour 1)
Write `lib/prompts/extraction-prompts.ts`. Prompts must instruct Claude to return **only valid JSON** matching the schema.

```typescript
export const WILL_EXTRACTION_PROMPT = `
Extract the following from this will document and return ONLY valid JSON matching this schema:
{
  "documentType": "will",
  "executorName": string,
  "beneficiaries": [{ "name": string, "share": string?, "specificBequest": string? }],
  "assets": [{ "description": string, "estimatedValue": number? }],
  "trustClauses": string[],
  "specialInstructions": string[],
  "codicils": string[],
  "rawChunks": string[]   // 3–5 sentence chunks for vector embedding
}
Do not include any text before or after the JSON.
`

export const BANK_STATEMENT_EXTRACTION_PROMPT = `...`
export const DEED_EXTRACTION_PROMPT = `...`
export const DOCUMENT_TYPE_DETECTION_PROMPT = `
Given this document, identify the type. Return ONLY one of: "will", "bank_statement", "deed", "insurance", "unknown".
`
```

### Phase 3 — Parsers (Hour 1–3)
Each parser: call Claude → validate with Zod → return typed extraction.

```typescript
// lib/parsers/will-parser.ts
import { anthropic } from "../claude"
import { WILL_EXTRACTION_PROMPT } from "../prompts/extraction-prompts"
import { WillExtractionSchema } from "../schemas/document-extractions"  // Member 2 owns schemas

export async function parseWill(documentText: string): Promise<WillExtraction> {
  const raw = await extractStructured(WILL_EXTRACTION_PROMPT, documentText, WillExtractionSchema)
  return raw
}
```

`document-router.ts` sends a snippet to Claude for type detection, then routes to the right parser.

### Phase 4 — Embeddings (Hour 3)
`lib/embeddings.ts` wraps OpenAI embeddings:

```typescript
import OpenAI from "openai"

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })

export async function embedChunks(chunks: string[]): Promise<number[][]> {
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: chunks,
  })
  return response.data.map(d => d.embedding)
}
```

### Phase 5 — Parse Document API Route (Hour 3–5)
`app/api/parse-document/route.ts` — the full pipeline:

```
POST /api/parse-document
  multipart form: file (PDF or image)

Flow:
1. formidable → extract file buffer
2. pdf-parse (PDF) or sharp (image) → get text / base64
3. document-router.ts → detect type
4. correct parser → extraction JSON
5. Member 3's Sentry wrapper → start transaction
6. embedChunks(extraction.rawChunks) → vectors
7. Member 2's redis.upsertVectors() → Redis Iris
8. Member 2's redis.mergeEstateState() → Redis KV
9. Trigger DeadlineAgent (call /api/deadline-agent internally)
10. Return { extraction, alerts }
```

---

## Key Interfaces (coordinate with Member 2)

You produce these — Member 2 writes the Zod schemas, you import them:

```typescript
// types/documents.ts (Member 2 owns types/, you define what goes in it)
type DocumentType = "will" | "bank_statement" | "deed" | "insurance" | "unknown"

interface WillExtraction {
  documentType: "will"
  executorName: string
  beneficiaries: { name: string; share?: string; specificBequest?: string }[]
  assets: { description: string; estimatedValue?: number }[]
  trustClauses: string[]
  specialInstructions: string[]
  codicils: string[]
  rawChunks: string[]
}

interface BankStatementExtraction {
  documentType: "bank_statement"
  institutionName: string
  accountLast4: string
  accountType: string
  balance: number
  statementDate: string
  transactions: { date: string; description: string; amount: number }[]
  rawChunks: string[]
}

interface DeedExtraction {
  documentType: "deed"
  propertyAddress: string
  apn: string                // Assessor Parcel Number
  legalDescription: string
  grantorName: string
  granteeName: string
  recordedDate: string
  estimatedValue?: number
  rawChunks: string[]
}
```

---

## Coordination Points

| You need from... | What |
|-----------------|------|
| **Member 2** | `lib/schemas/document-extractions.ts` Zod schemas — import these to validate Claude output |
| **Member 2** | `lib/redis.ts` with `upsertVectors()` and `mergeEstateState()` functions — call these in your API route |
| **Member 3** | `lib/sentry.ts` `withSentryTransaction()` wrapper — wrap your Claude calls |
| **Member 4** | Nothing yet — they consume your API route |

| Others need from you | What |
|--------------------|------|
| **Member 4** | Working `POST /api/parse-document` endpoint that returns `{ extraction, alerts }` |
| **Member 3** | `streamChat()` from `lib/claude.ts` (already exported) |
| **Everyone** | `anthropic` client from `lib/claude.ts` |

---

## Acceptance Criteria

- [ ] `lib/claude.ts` exports `anthropic`, `extractStructured()`, and `streamChat()`
- [ ] `lib/embeddings.ts` exports `embedChunks(chunks: string[]): Promise<number[][]>`
- [ ] `POST /api/parse-document` accepts a PDF, returns extraction JSON + any new alerts
- [ ] Will parser extracts: executorName, beneficiaries, assets, rawChunks
- [ ] Bank parser extracts: institutionName, accountLast4, balance, rawChunks
- [ ] Deed parser extracts: propertyAddress, estimatedValue, rawChunks
- [ ] All Claude outputs Zod-validated before writing to Redis
- [ ] document-router.ts correctly identifies "will", "bank_statement", "deed"

---

## Sponsor Requirements You Unlock

- **Anthropic track**: Claude doing hard reasoning on document extraction (vision + structured output)
- **Redis track**: You write the embeddings that power vector search — make sure `rawChunks` are meaningful 3–5 sentence segments, not entire documents
- **Sentry track**: Wrap every `extractStructured()` call with `withSentryTransaction({ action: "document_parse", estate_id, doc_type })`
