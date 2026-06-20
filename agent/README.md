# Agent Service

Python service for document intelligence, estate memory, RAG chat, DeadlineAgent, and
letter generation.

## Ownership

- Member 1: `llm/`, `documents/`, extraction prompts, `/parse-document`
- Member 2: `schemas/`, `store/`, `seed/`, data contracts
- Member 3: `agents/`, `rules/`, `observability/`, chat, letters

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

The current store and AI helpers include in-memory/offline placeholders. Add real Redis,
Claude, embeddings, and Phoenix behavior behind the existing module functions.

