# Web App

Next.js 14 frontend for Executor AI: auth (login / register), dashboard, estate-aware
chat, document upload, voice, and generated letters. It talks to the Python agent only
through a thin Sentry-wrapped proxy (`app/api/agent/[...path]`) plus dedicated auth and
voice routes.

## Layout

- `app/` — pages (`welcome`, dashboard, `chat`, `upload`) and route handlers
  (`api/auth/*`, `api/voice/*`, `api/agent/*`)
- `components/` — `screens/` (AppShell, Dashboard, Chat, Letters, Upload, …), the `ds/`
  design system, and shared widgets (AlertBanner, VoiceButton, …)
- `lib/` — `agentClient.ts`, `deepgram.ts`, `sentry.ts`, `design/`, and Zod schemas
- `types/` — TypeScript contracts mirroring the Pydantic models

## Local Run

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

The API proxy expects the Python service at `AGENT_API_URL`, defaulting to
`http://localhost:8000`.

