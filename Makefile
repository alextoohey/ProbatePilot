# ClearPath Estate — Dev Commands
# Run from the repo root.

.PHONY: install install-agent install-web dev dev-agent dev-web seed test test-agent test-web-contracts typecheck lint help

# ── Setup ────────────────────────────────────────────────────────────────────

install: install-agent install-web  ## Install all dependencies (Python + Node)

install-agent:  ## Install Python deps via uv
	cd agent && uv sync

install-web:  ## Install Node deps
	cd web && npm install

# Copy env files if they don't exist yet
env:  ## Copy .env examples (safe — never overwrites existing files)
	@test -f agent/.env || (cp agent/.env.example agent/.env && echo "Created agent/.env — fill in your API keys")
	@test -f web/.env.local || (cp web/.env.local.example web/.env.local && echo "Created web/.env.local — fill in your API keys")

# ── Dev servers ───────────────────────────────────────────────────────────────

dev:  ## Start both services in parallel (requires agent + web installed)
	@echo "Starting agent (port 8000) and web (port 3000)..."
	@trap 'kill 0' SIGINT; \
	  cd agent && uv run uvicorn main:app --reload --port 8000 & \
	  cd web && npm run dev & \
	  wait

dev-agent:  ## Start the Python FastAPI service only (port 8000)
	cd agent && uv run uvicorn main:app --reload --port 8000

dev-web:  ## Start the Next.js frontend only (port 3000)
	cd web && npm run dev

# ── Demo helpers ──────────────────────────────────────────────────────────────

seed:  ## Reset the demo estate to a known-good state (agent must be running)
	curl -s -X POST http://localhost:8000/seed | python3 -m json.tool

health:  ## Check the agent is up
	curl -s http://localhost:8000/health

# ── Code quality ──────────────────────────────────────────────────────────────

test: test-agent test-web-contracts  ## Run Python and TypeScript contract tests

test-agent:  ## Run Member 1/2 Python and integration tests
	cd agent && STORE_BACKEND=memory uv run pytest ../tests/member1 ../tests/member2 ../tests/integration

test-web-contracts:  ## Run TypeScript/Zod contract tests
	cd web && npm run test:contracts

typecheck:  ## TypeScript typecheck (web)
	cd web && npm run typecheck

lint:  ## Lint web TypeScript
	cd web && npm run lint

# ── Help ──────────────────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
