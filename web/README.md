# Web App

Next.js frontend for the Executor AI dashboard, chat, upload, voice, and generated
letters.

## Ownership

- Member 4 owns `app/`, `components/`, `lib/agentClient.ts`, voice routes, and UI polish.
- Member 2 owns the TS contracts in `types/` and Zod schemas in `lib/schemas/`.

## Local Run

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

The API proxy expects the Python service at `AGENT_API_URL`, defaulting to
`http://localhost:8000`.

