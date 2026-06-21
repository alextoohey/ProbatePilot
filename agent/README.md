# Agent Service

Python service for document intelligence, estate memory, RAG chat, DeadlineAgent, and
letter generation.

## Ownership

- Member 1: `llm/`, `documents/`, extraction prompts, `/parse-document`
- Member 2: `schemas/`, `store/`, `seed/`, data contracts
- Member 3: `agents/`, `rules/`, `observability/`, chat, letters

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

The current store and AI helpers include in-memory/offline placeholders. Add real Redis,
Claude, embeddings, and Phoenix tracing behavior behind the existing module functions.

## Phoenix tracing

The service sends Anthropic, OpenAI embedding, and custom workflow spans to Phoenix.
Start a Phoenix server on `http://localhost:6006`, or configure Phoenix Cloud in `.env`:

```bash
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=executor-ai-agent
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
