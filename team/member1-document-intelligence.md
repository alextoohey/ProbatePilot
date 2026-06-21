# Member 1 — Document Intelligence (Python)

**Owner**: Alex
**Language**: Python (`agent/`)
**Track dependency**: Everything downstream depends on a populated estate state. Your
pipeline is what fills it. Ship the parser first and unblock the team.

---

## Your Mission
You own the pipeline that turns a raw uploaded file into structured estate data. A will,
bank statement, or deed comes in; Claude reads it, you validate the result, embed the
useful chunks, and write everything to Redis. Without this there is no estate state, no
RAG, and no agent. This is the foundation — build it first.

You also own the **shared Claude client** in `agent/llm/`, which Members 2 and 3 import.

---

## What You Own
```
agent/
├── llm/
│   ├── claude.py            # Anthropic client + shared helpers (extract / stream / agent)
│   └── embeddings.py        # OpenAI text-embedding-3-small calls
├── documents/
│   ├── router.py            # Detect document type, dispatch to the right parser
│   ├── will.py              # Will extraction
│   ├── bank_statement.py    # Bank statement extraction
│   └── deed.py              # Deed extraction
└── prompts/
    └── extraction.py        # Per-document-type extraction prompts
```
Plus the `POST /parse-document` route registered in `agent/main.py`.

---

## How To Approach It

### The shared Claude client (`agent/llm/claude.py`)
Build this first; the whole team imports it. It should expose a small, stable surface:
- a configured Anthropic client (reads `ANTHROPIC_API_KEY` from the environment),
- a **structured-extraction** helper that takes a prompt + content (text, or an
  image/PDF block) + a Pydantic model, and returns a validated instance. Use the SDK's
  structured-output parsing so Claude's output is typed, not hand-parsed JSON.
- a **streaming-chat** helper (used by Member 3's chat endpoint),
- a place to plug in the agent tool-use loop (Member 3 owns the loop itself).

Model guidance: use `claude-sonnet-4-6` for document parsing (vision + structured output,
higher volume). Leave `claude-opus-4-8` for the agent/chat reasoning paths. Every call
must run inside a Phoenix span — coordinate the span helper with Member 3.

### Embeddings (`agent/llm/embeddings.py`)
A thin wrapper over OpenAI `text-embedding-3-small` that turns a list of chunks into a
list of vectors. Keep it batch-friendly.

### Extraction prompts (`agent/prompts/extraction.py`)
One prompt per document type, plus a short type-detection prompt. Each prompt should make
Claude return exactly the fields in the corresponding Pydantic model and produce
`rawChunks` — 3–5 sentence segments meant for embedding (not whole documents; meaningful,
self-contained spans). Prefer the SDK's structured-output path over "return only JSON"
instructions.

### Parsers (`agent/documents/`)
Each parser: take document content, call the structured-extraction helper with its prompt
and Pydantic model, return the validated extraction. The router sends a snippet to Claude
for type detection, then dispatches to the right parser. Handle the `unknown` case gracefully.

### The parse pipeline (`POST /parse-document`)
Accept a multipart file upload, then:
1. Extract text (PDF) or prepare image/PDF content blocks for Claude vision (scans).
2. Detect the document type → run the matching parser → get a validated extraction.
3. Embed `rawChunks` and upsert them to Redis Vector Sets (Member 2's helper), scoped by
   `estateId`.
4. Merge the structured facts into estate state (Member 2's merge helper).
5. Trigger the DeadlineAgent to re-evaluate (Member 3's entrypoint).
6. Return `{ extraction, alerts }`.

Wrap the Claude call(s) in a Phoenix span tagged `action=document_parse` and `doc_type`.

---

## Contracts (agree these with Member 2)
You produce typed extractions; Member 2 owns the canonical Pydantic models in
`agent/schemas/`. Settle the field list **together, early**: each extraction carries the
structured facts for its document type plus `rawChunks: list[str]`. Examples of the facts
you should pull:
- **Will** — executor name, beneficiaries (name, share, specific bequests), assets,
  trust clauses, special instructions, codicils.
- **Bank statement** — institution, account last-4, account type, balance, statement date,
  notable transactions.
- **Deed** — property address, APN, legal description, grantor/grantee, recorded date,
  estimated value.

---

## Coordination
| You need from… | What |
|----------------|------|
| **Member 2** | Pydantic extraction models (`agent/schemas/`); Redis `upsert_vectors` and `merge_estate_state` helpers |
| **Member 3** | The Phoenix span helper to wrap Claude calls; the DeadlineAgent entrypoint to call after a parse |

| Others need from you | What |
|----------------------|------|
| **Member 3** | The shared Claude client (`agent/llm/claude.py`): extraction + streaming helpers |
| **Member 2** | Agreement on the extraction field shapes |
| **Member 4** | A working `POST /parse-document` returning `{ extraction, alerts }` |

---

## Acceptance Criteria
- [ ] `agent/llm/claude.py` exposes a configured client, a structured-extraction helper,
      and a streaming-chat helper.
- [ ] `agent/llm/embeddings.py` turns chunks into vectors via `text-embedding-3-small`.
- [ ] `POST /parse-document` accepts a PDF, returns a validated extraction + any new alerts.
- [ ] Will / bank / deed parsers each extract their key fields + meaningful `rawChunks`.
- [ ] The router correctly identifies will, bank statement, and deed.
- [ ] Every Claude output is Pydantic-validated before anything is written to Redis.

---

## Sponsor Hooks You Unlock
- **Anthropic** — Claude doing hard vision + structured extraction on real documents.
- **Redis** — your chunks power vector search; keep them meaningful, per-`estateId`.
- **Phoenix** — your parse calls are the first traced spans; a bad extraction should be
  visible in Phoenix and drive a prompt fix during the build.
