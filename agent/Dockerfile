# ProbatePilot agent service — FastAPI + uv.
#
# Build from the repo root so the Dockerfile can COPY only the agent/
# directory:
#   docker build -f agent/Dockerfile -t probatepilot-agent .
#
# Runs with STORE_BACKEND=memory by default, so the only required env var
# to boot is ANTHROPIC_API_KEY. See docs/DEPLOYMENT.md for the full list.

FROM python:3.12-slim AS base

# uv ships as a static binary; copying it in is faster and more reliable
# than pip-installing it.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY agent/ .
RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1 \
    STORE_BACKEND=memory \
    PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# uvicorn runs directly from the venv already on PATH — not via `uv run`,
# which re-checks/re-syncs the lockfile (including dev-only deps) on every
# container start. Shell form so $PORT (set by Render, Railway, etc.) is
# honored; falls back to 8000 for `docker run` without -e PORT=...
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
