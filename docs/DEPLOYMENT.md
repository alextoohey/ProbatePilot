# Deployment

ProbatePilot is two services: the Python agent (`agent/`) and the Next.js
frontend (`web/`). Deploy the agent first, then point the frontend at it.

Everything here is optional beyond `ANTHROPIC_API_KEY` — the app is designed
to degrade gracefully. See the [env var reference](../CLAUDE.md#environment-variables)
for what each key unlocks.

## 1. Deploy the agent (Render)

A `render.yaml` blueprint is included at the repo root.

1. Push this repo to your own GitHub account.
2. In the [Render dashboard](https://dashboard.render.com), choose **New +** →
   **Blueprint**, and point it at your fork.
3. Render reads `render.yaml` and provisions a free web service from
   `agent/Dockerfile`. It will prompt for `ANTHROPIC_API_KEY` (required) and
   `OPENAI_API_KEY` / `RESEND_API_KEY` (optional) at first deploy.
4. Once live, note the service URL (`https://probatepilot-agent-xxxx.onrender.com`).
   Confirm it's healthy: `curl https://<your-service>.onrender.com/health`.

**Any Docker host works the same way** — `agent/Dockerfile` builds standalone
(`docker build -f agent/Dockerfile -t probatepilot-agent .` from the repo
root) and reads `$PORT` at runtime, so Railway, Fly.io, and Cloud Run all work
without changes.

The default `STORE_BACKEND=memory` means estate data lives in the container's
memory and resets on restart — fine for a demo. For persistence, provision a
[Redis Cloud](https://redis.io/cloud/) instance (Redis 8, for its Vector Sets
support) and set `STORE_BACKEND=redis_cloud` + `REDIS_URL=rediss://...`.

## 2. Deploy the frontend (Vercel)

1. In [Vercel](https://vercel.com/new), import the same fork with **Root
   Directory** set to `web/`.
2. Set the one required env var:
   - `AGENT_API_URL` = the Render service URL from step 1
3. Optional env vars (voice and error tracking degrade cleanly without them):
   `DEEPGRAM_API_KEY`, `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_DSN`, `SENTRY_ORG`,
   `SENTRY_PROJECT`, `NEXT_PUBLIC_APP_URL` (your Vercel URL, used for
   metadata/share links).
4. Deploy. Vercel auto-detects Next.js — no build config needed.

## 3. Seed the demo estate

The live app is empty until the demo estate exists. Either:

- Click **Try the demo** on the deployed `/welcome` page (this calls
  `POST /auth/demo` on the agent, which seeds it on first use), or
- Seed it directly: `curl -X POST https://<your-agent>.onrender.com/seed`

## Notes

- **Free-tier cold starts**: Render's free plan spins down after 15 minutes
  idle and takes ~30–60s to wake on the next request. The first load after
  idle will feel slow — this is Render, not the app.
- **CORS**: the frontend never calls the agent directly from the browser —
  every request is proxied through Next.js API routes (`web/app/api/agent/[...path]`),
  which forward the session cookie as a Bearer token server-side. No CORS
  configuration is needed on the agent.
- **Auth**: every estate-scoped endpoint requires a session and ownership,
  except the seeded demo estate, which stays world-readable so the "Try the
  demo" flow works without registration. See `agent/api/deps.py`.
