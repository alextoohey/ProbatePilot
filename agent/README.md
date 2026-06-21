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
```

The example environment hides estate inputs, outputs, and message content by default.
After starting the service, `GET /health` reports whether Phoenix and both SDK
instrumentors initialized successfully.
