# Member 3 — DeadlineAgent + Reasoning (Python)

**Owner**: Sameer
**Language**: Python (`agent/`)
**Track dependency**: The DeadlineAgent is the product moat — the thing that makes
ClearPath an agent, not a chatbot. Your alerts are the hero of the demo. You also own the
RAG chat endpoint and the Arize tracing that wins the observability prize.

---

## Your Mission
You own the proactive intelligence layer. The DeadlineAgent reads estate state, reasons
over California probate rules and liability triggers, and fires ranked alerts before the
executor makes an expensive mistake. You also own the **RAG chat endpoint** (the
conversational counterpart to the agent), **letter generation**, and **Arize Phoenix**
tracing across the whole Python service.

This is the most reasoning-heavy role. Lean on `claude-opus-4-8` and adaptive thinking.

---

## What You Own
```
agent/
├── agents/
│   └── deadline_agent.py     # The Claude tool-use agent loop
├── rules/
│   └── california_probate.py # The hardcoded CA probate ruleset (11 rules)
├── prompts/
│   ├── system.py             # Base chat system prompt (assembled per request)
│   └── letters.py            # Letter-generation prompts (5+ letter types)
└── observability/
    └── phoenix.py            # Arize Phoenix / OpenInference setup + span helper
```
Plus the routes in `agent/main.py`: `POST /deadline-agent`, `POST /chat` (SSE),
`POST /generate-letter`.

---

## How To Approach It

### Arize Phoenix first (~30 min, `agent/observability/phoenix.py`)
Stand this up before anything else — it's cheap and it wins a prize. Initialize Phoenix /
OpenInference so Anthropic calls are auto-instrumented, and expose a small span helper the
whole team wraps Claude calls in. Standard attributes across all spans:
`estate_id`, `action_type` (`document_parse` | `chat_query` | `deadline_agent_run` |
`letter_generation`), plus `doc_type`, `rule_checked`, `alerts_fired` where relevant.
Member 1's parse calls and Member 4-facing chat calls all flow through this.

### California probate rules (`agent/rules/california_probate.py`)
A typed data file: the 11 rules from
[project_overview.md §6](../project_overview.md#6-california-probate-rules-database). Each
rule carries an id, human title, statute citation, the trigger field, the deadline window,
and a way to evaluate it against an estate (compute days-remaining with `dateutil`, decide
severity, and produce an Alert or nothing). Keep the rule *data* declarative so the agent
can reason over it.

The 11 rules: DE-140 petition, death certificates, DE-160 inventory, creditor notification,
newspaper notice, creditor claim period, estate EIN, final 1040, Form 1041, debt payment
order, property appraisal.

### The DeadlineAgent (`agent/agents/deadline_agent.py`) — the moat
This must be a **real agent**, not a for-loop. Build it as a Claude **tool-use loop**:
expose the rule evaluations (and estate-state reads) as typed tools, give Claude the estate
and the ruleset, and let it iterate — checking rules, computing days-remaining, deciding
severity, deduplicating against existing alerts, and (crucially) reasoning about
**cross-rule consequences** (e.g. "no appraisal blocks the DE-160 filing," "distributing
before creditor notification creates personal liability"). Use `claude-opus-4-8` with
adaptive thinking. Output a ranked `Alert[]` (critical first), write it back through
Member 2's helper, and record `rules_checked` / `alerts_fired` on the Phoenix span.

On fresh demo seed data it must produce the two CRITICAL alerts (DE-160 and creditor
notification). The SDK's tool-runner handles the loop mechanics; you own the tool design
and the reasoning prompt.

### RAG chat (`POST /chat`, streamed)
The conversational endpoint. Embed the incoming message (Member 1's helper), vector-search
Redis (Member 2's helper, filtered by `estateId`), load estate state, and assemble the
system prompt (`agent/prompts/system.py`,
[project_overview.md §8](../project_overview.md#8-system-prompt-template)). **Prompt-cache**
the stable prefix (base instructions + estate state) so repeated turns are cheap. Stream
Claude's response back as Server-Sent Events for the web layer to consume. Wrap in a
Phoenix span `action=chat_query`.

### Letters (`POST /generate-letter`, `agent/prompts/letters.py`)
5+ letter types (creditor notice, bank notification, IRS EIN request, beneficiary update,
property transfer). Each prompt injects estate-specific variables and produces a formatted,
sign-ready letter. Use `claude-sonnet-4-6`. Cite the relevant statute where appropriate
(e.g. CA Probate Code §9051 for creditor notices). Wrap in a span `action=letter_generation`.

---

## Coordination
| You need from… | What |
|----------------|------|
| **Member 1** | The shared Claude client (extraction + streaming helpers) |
| **Member 1** | The embeddings helper (for the chat RAG step) |
| **Member 2** | `get_estate_state`, `write_alerts`, `get_alerts`, vector search; EstateState + Alert models |

| Others need from you | What |
|----------------------|------|
| **Member 1** | The Phoenix span helper; the DeadlineAgent entrypoint to call after a parse |
| **Member 4** | `POST /deadline-agent` (alerts), `POST /chat` (SSE), `POST /generate-letter` |
| **Everyone** | Phoenix wired up so all Claude calls are traced |

---

## Acceptance Criteria
- [ ] Phoenix initialized; a span helper the whole team uses; spans carry `estate_id` +
      `action_type`.
- [ ] All 11 CA probate rules implemented as declarative rule data.
- [ ] The DeadlineAgent is a Claude tool-use loop (not a hand-rolled for-loop) and returns
      the 2 CRITICAL alerts on fresh seed data.
- [ ] `POST /deadline-agent` returns a ranked alert list.
- [ ] `POST /chat` streams a response grounded in estate state + retrieved chunks (SSE),
      with the stable prompt prefix cached.
- [ ] `POST /generate-letter` returns a formatted creditor-notice letter with the right
      names, dates, and statute.

---

## Sponsor Hooks You Unlock
- **Anthropic** — the DeadlineAgent is Claude doing proactive, multi-step reasoning, not
  Q&A. It is the core demo moment and the strongest argument for the prize.
- **Arize** — your Phoenix setup traces every call across the service. In the demo, show
  the Phoenix dashboard with the agent loop, token counts, and `alerts_fired` — and ideally
  a moment where a trace caught a bad extraction or slow tool call and you fixed it.
- **Redis** — every chat turn runs a real vector search; the agent reads estate memory
  from Redis on every run.
