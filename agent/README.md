# Agent Service

Python FastAPI service: auth, document intelligence, estate memory, RAG chat, the
DeadlineAgent and ResearchAgent, letter generation, and email notifications. Runs entirely
on `claude-sonnet-4-6` today (see `DOCUMENT_MODEL` / `REASONING_MODEL` in
`llm/claude.py`). See [the root CLAUDE.md](../CLAUDE.md#api-surface) for the full route
list.

## Layout

- `llm/` — Anthropic client (extract / stream / agent helpers) + OpenAI embeddings
- `documents/` — router + will / bank statement / deed / creditor-notice parsers
- `agents/` — the DeadlineAgent tool-use loop
- `researcher/` — the weekly probate-law ResearchAgent
- `rules/` — the California probate ruleset
- `schemas/` — Pydantic contracts (estate, api, documents, auth)
- `store/` — KV + vector boundary (memory / Redis Cloud / Upstash)
- `auth/` — bcrypt password hashing + cookie sessions
- `notify/` — Resend weekly recap / alert digest
- `observability/` + `evals/` — Phoenix tracing and the LLM-as-judge eval
- `seed/` — demo estate reset

## Local Run

```bash
# From the repo root (recommended)
make install-agent   # uv sync
make dev-agent       # uvicorn main:app --reload --port 8000

# Or directly from this directory
uv sync
cp .env.example .env   # fill in keys
uv run uvicorn main:app --reload --port 8000
```

The store defaults to `STORE_BACKEND=memory`, so the service boots and runs offline; set
`STORE_BACKEND=redis_cloud` (or `upstash`) with the matching credentials for a real store.
AI helpers no-op gracefully when `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` are unset, so the
deterministic fallbacks still serve the demo.

## Phoenix tracing

The service sends Anthropic, OpenAI embedding, and custom workflow spans to Phoenix.
Start a Phoenix server on `http://localhost:6006`, or configure Phoenix Cloud in `.env`:

```bash
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=executor-ai-agent
PHOENIX_API_KEY=  # required only when the Phoenix endpoint requires authentication
```

The example environment hides estate inputs, outputs, and message content by default.
The collector setting accepts either a Phoenix base URL or a full `/v1/traces` URL.
After starting the service, `GET /health` reports whether Phoenix and both SDK
instrumentors initialized successfully.

### DeadlineAgent quality evaluator

To capture the evidence needed to judge DeadlineAgent outputs, opt in and restart the
agent:

```bash
PHOENIX_CAPTURE_EVAL_CONTEXT=true
PHOENIX_EVAL_PROVIDER=anthropic
PHOENIX_EVAL_MODEL=claude-sonnet-4-6
```

Run `/deadline-agent` at least once, then evaluate captured spans and write the 1-5 score
plus explanation back to Phoenix:

```bash
make eval-deadline
# or
uv run python -m evals.deadline_next_steps_quality --limit 500
```

Only spans named `deadline_agent.run` with matching DeadlineAgent metadata and evaluation
payloads are selected. Use `--hours 24` to limit the time window or `--no-log` to preview
scores without creating Phoenix annotations. Evaluation snapshots contain estate facts;
leave `PHOENIX_CAPTURE_EVAL_CONTEXT=false` when continuous evaluation is not required.
