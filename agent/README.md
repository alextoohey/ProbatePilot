# Agent Service

Python FastAPI service: auth, document intelligence, estate memory, RAG chat, the
DeadlineAgent and ResearchAgent, letter generation, and email notifications. Runs entirely
on `claude-sonnet-4-6` today (see `DOCUMENT_MODEL` / `REASONING_MODEL` in
`llm/claude.py`). See [the root CLAUDE.md](../CLAUDE.md#api-surface) for the full route
list.

## Layout

- `main.py` — app factory only; every route lives in `api/routers/`
- `api/` — FastAPI routers (one file per domain) + auth/ownership dependencies
- `llm/` — Anthropic client (extract / stream / agent helpers) + OpenAI embeddings
- `documents/` — type router, will / bank statement / deed / creditor-notice parsers,
  and the upload → extract → merge → embed pipeline
- `agents/` — the DeadlineAgent tool-use loop
- `researcher/` — the weekly probate-law ResearchAgent
- `rules/` — the California probate ruleset
- `schemas/` — Pydantic contracts (estate, api, documents, auth)
- `store/` — domain layer (`redis_client.py`) + backend implementations
  (`store/backends/`: memory / Redis Cloud / Upstash)
- `auth/` — bcrypt password hashing + cookie sessions
- `notify/` — Resend weekly recap / alert digest
- `observability/` + `evals/` — Phoenix tracing and the LLM-as-judge eval
- `seed/` — demo estate reset
- `constants.py` — small cross-cutting constants (e.g. `DEFAULT_ESTATE_ID`)

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

The service sends Anthropic, OpenAI embedding, and custom workflow spans to Phoenix. This
is entirely optional — without a collector running, the SDK just logs a connection warning
and moves on; nothing in the app depends on Phoenix being up.

To actually see traces, run a local Phoenix server with Docker:

```bash
docker run -p 6006:6006 -p 4317:4317 -i -t arizephoenix/phoenix:latest
```

Then open `http://localhost:6006` — traces from the agent show up there automatically,
since `agent/.env.example` already points `PHOENIX_COLLECTOR_ENDPOINT` at that address.
No Phoenix account or API key needed for local use. To use Phoenix Cloud instead, set these
in `.env`:

```bash
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=probatepilot-agent
PHOENIX_API_KEY=  # required only when the Phoenix endpoint requires authentication
PHOENIX_CAPTURE_LLM_CONTENT=true
```

The demo configuration captures LLM prompts, tool calls, and completions so they are
inspectable in Phoenix. Set `PHOENIX_CAPTURE_LLM_CONTENT=false` when estate content
must be redacted. This explicit setting takes precedence over ambient
`OPENINFERENCE_HIDE_*` variables when the service initializes its instrumentors.
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
