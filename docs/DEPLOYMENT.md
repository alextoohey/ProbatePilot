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

## Known follow-up: Next.js / Sentry major version upgrade

`npm audit` currently reports advisories against `next` (`^14.2.0`) and
`@sentry/nextjs` (`^8.30.0`) — both packages are already pinned to the newest
release in their installed major version (`next@14.2.35`, `@sentry/nextjs@8.55.2`),
so there's no drop-in patch available; clearing these requires a major-version
upgrade (`next` 14→16, `@sentry/nextjs` 8→10) with real breaking-change review
(App Router changes, Sentry config API changes), not a one-command fix. Several
of the `next` advisories are specifically about self-hosted production behavior
(request smuggling in rewrites, SSRF via WebSocket upgrades, cache poisoning),
so this is worth doing as a dedicated, tested piece of work before this app
handles real traffic — not folded into an unrelated change.

## Known follow-up: Email delivery

The email pipeline (`agent/notify/email.py`) is fully built and tested — real Resend
integration, human-toned weekly recap / alert digest templates, graceful degradation to a
preview when unconfigured. The "Send weekly recap" and "Email me copies" controls are
hidden in the UI (`EMAIL_NOTIFICATIONS_ENABLED = false` in
`web/components/screens/NotificationsMenu.tsx`) rather than shipped half-working, for one
specific reason: Resend's sandbox sender (`onboarding@resend.dev`) only delivers to the
account owner's own address until a domain is verified. Without that, the feature would
only ever work for whoever owns the Resend account — not an arbitrary logged-in user or a
recruiter trying the demo — which reads as broken rather than gated.

To turn it back on once a domain is available:

1. Buy or claim a domain (GitHub Student Developer Pack includes a free `.me` domain via
   Namecheap if eligible; otherwise a cheap TLD from Namecheap/Porkbun/Cloudflare runs
   $1–15/year).
2. Verify it with Resend (Dashboard → Domains → Add Domain, then add the SPF/DKIM DNS
   records they provide).
3. Set `EMAIL_FROM=ProbatePilot <notifications@yourdomain.com>` in `agent/.env` and
   restart the agent — `send_email()` already passes `EMAIL_FROM` straight through to
   Resend's `from` field, so no code change is needed there.
4. Flip `EMAIL_NOTIFICATIONS_ENABLED` back to `true` in `NotificationsMenu.tsx`.
5. Make sure `NOTIFY_OVERRIDE_RECIPIENT` is unset in the deployed environment — it's a
   local-testing escape hatch that forces every recipient to one address, which would
   misroute every real user's email to the developer's inbox if left on.

This is a "buy/verify a domain" gap, not an engineering one — worth revisiting once this
is actually deployed and worth the ~$10-15/year, not before.
