# Web App

Next.js 14 frontend for ProbatePilot: auth (login / register), dashboard, estate-aware
chat, document upload, voice, and generated letters. It talks to the Python agent only
through a thin Sentry-wrapped proxy (`app/api/agent/[...path]`) plus dedicated auth and
voice routes.

## Layout

- `app/` — `welcome` (marketing landing + auth) and `/` (the app shell — dashboard, chat,
  upload, and letters all live as tabs inside it, not separate routes) plus route handlers
  (`api/auth/*`, `api/voice/*`, `api/agent/*`)
- `components/screens/` — AppShell, Dashboard, Chat, Letters, Upload, AuthLanding, and the
  modals; `components/ds/` — the design-system primitives
- `lib/` — `agentClient.ts` (the one place that calls the agent), `deepgram.ts`,
  `sentry.ts`, `design/`, and Zod schemas
- `types/` — TypeScript contracts mirroring the Pydantic models

## Local Run

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

The API proxy expects the Python service at `AGENT_API_URL`, defaulting to
`http://localhost:8000`.

