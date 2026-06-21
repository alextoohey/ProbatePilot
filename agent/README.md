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
Claude, embeddings, and Arize AX tracing behavior behind the existing module functions.
