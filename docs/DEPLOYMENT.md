# Deployment

ProbatePilot is two services: the Python agent (`agent/`) and the Next.js
frontend (`web/`). Deploy the agent first, then point the frontend at it.

Everything here is optional beyond `ANTHROPIC_API_KEY` and `REDIS_URL` — the app is
designed to degrade gracefully. See [`agent/.env.example`](../agent/.env.example) and
[`web/.env.local.example`](../web/.env.local.example) for the full, authoritative list of
what each key unlocks.

## 1. Deploy the agent

Two documented paths. **Cloud Run is the recommended default** — measured against the real
deployed service after 12 minutes idle: a **14s** cold start, versus Render free tier's
~30-60s (see the Notes section below for the measurement and why the gap matters for a
recruiter clicking a cold link). Render is documented as the simpler alternative if you'd
rather not touch the `gcloud` CLI.

Either way, first: provision a [Redis Cloud](https://redis.io/cloud/) instance (Redis 8,
for its Vector Sets support — the free tier is enough) and push this repo to your own
GitHub account. You'll need the Redis connection string for both paths below. Never put a
real value in a committed file — see
[`docs/database.md`](database.md#never-commit-a-real-redis_url) for why.

### Option A: Google Cloud Run (recommended — fast cold starts)

`agent/Dockerfile` needs zero changes — it already reads `$PORT` at runtime exactly the
way Cloud Run requires (verified locally this session: `docker run -e PORT=10000 ...`
correctly served on the injected port).

1. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), then:
   ```bash
   gcloud auth login
   gcloud projects create your-project-id   # or use an existing project
   gcloud config set project your-project-id
   gcloud services enable run.googleapis.com artifactregistry.googleapis.com
   ```
2. Create a one-time Artifact Registry repo to hold the image, and authenticate Docker
   against it:
   ```bash
   gcloud artifacts repositories create probatepilot \
     --repository-format=docker --location=us-west1
   gcloud auth configure-docker us-west1-docker.pkg.dev
   ```
3. Build and push, using the exact same build command already verified working this
   session (repo root as build context, `agent/Dockerfile` as the Dockerfile path):
   ```bash
   docker build -f agent/Dockerfile \
     -t us-west1-docker.pkg.dev/your-project-id/probatepilot/agent:latest .
   docker push us-west1-docker.pkg.dev/your-project-id/probatepilot/agent:latest
   ```
4. Deploy it:
   ```bash
   gcloud run deploy probatepilot-agent \
     --image us-west1-docker.pkg.dev/your-project-id/probatepilot/agent:latest \
     --region us-west1 --allow-unauthenticated \
     --set-env-vars STORE_BACKEND=redis_cloud
   ```
5. Add the secret env vars through the Cloud Console instead of the CLI (Cloud Run service
   → **Edit & Deploy New Revision** → **Variables & Secrets**), so they don't land in your
   shell history: `ANTHROPIC_API_KEY`, `REDIS_URL` (both required), `OPENAI_API_KEY`
   (optional). For real secret hygiene beyond that, Cloud Run integrates with Secret
   Manager (`--set-secrets` instead of `--set-env-vars`) — worth doing if you want to go
   further, not required to get this running.
6. Once live, note the service URL (`https://probatepilot-agent-xxxx-uw.a.run.app`).
   Confirm it's healthy: `curl https://<your-service>.run.app/health`.

**Caveat:** `gcloud` CLI flags and Cloud Run/Artifact Registry free-tier terms shift over
time, and this wasn't run against a live GCP account to confirm end-to-end — cross-check
against [Cloud Run's own quickstart](https://cloud.google.com/run/docs/quickstarts) if any
command above doesn't behave as written.

### Option B: Render (simpler, slower cold starts)

A `render.yaml` blueprint is included at the repo root.

1. In the [Render dashboard](https://dashboard.render.com), choose **New +** →
   **Blueprint**, and point it at your fork.
2. Render reads `render.yaml` and provisions a free web service from
   `agent/Dockerfile`. It will prompt for `ANTHROPIC_API_KEY` and `REDIS_URL` (both
   required) and `OPENAI_API_KEY` (optional) at first deploy.
3. Once live, note the service URL (`https://probatepilot-agent-xxxx.onrender.com`).
   Confirm it's healthy: `curl https://<your-service>.onrender.com/health`.

**Any Docker host works the same way** — `agent/Dockerfile` builds standalone
(`docker build -f agent/Dockerfile -t probatepilot-agent .` from the repo
root) and reads `$PORT` at runtime, so Railway and Fly.io work without changes too.

**Why Redis Cloud instead of the default `STORE_BACKEND=memory`, on either path:** the
memory backend keeps all estate data, including real registered accounts (not just the
demo estate), in the container's RAM. Both Render's free tier (idle spin-down) and Cloud
Run's scale-to-zero (the same idea, just faster) start a clean process on the next
request — memory-backed data doesn't survive that, so a real account made yesterday would
just be gone. `render.yaml` defaults to `STORE_BACKEND=redis_cloud` for exactly this
reason, and the Cloud Run steps above set it explicitly; `memory` is still fine for local
dev or a throwaway demo where that reset is acceptable.

## 2. Deploy the frontend (Vercel)

1. In [Vercel](https://vercel.com/new), import the same fork with **Root
   Directory** set to `web/`.
2. Set the one required env var:
   - `AGENT_API_URL` = the agent's service URL from step 1 (Cloud Run or Render)
3. Optional env vars (voice and error tracking degrade cleanly without them):
   `DEEPGRAM_API_KEY`, `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_DSN`, `SENTRY_ORG`,
   `SENTRY_PROJECT`, `NEXT_PUBLIC_APP_URL` (your Vercel URL, used for
   metadata/share links).
4. Deploy. Vercel auto-detects Next.js — no build config needed.

## 3. Seed the demo estate

The live app is empty until the demo estate exists. Either:

- Click **Try the demo** on the deployed `/welcome` page (this calls
  `POST /auth/demo` on the agent, which seeds it on first use), or
- Seed it directly: `curl -X POST https://<your-agent-url>/seed`

## Notes

- **Cold starts**: both paths scale to zero when idle, so the first request after a quiet
  period always pays a startup cost — the question is how much. Measured directly against
  this app's real deployed Cloud Run service: **13.99s** after 12 minutes idle
  (`curl -w "%{time_total}"` against `/health`) — slower than Cloud Run's reputation for
  "low single-digit seconds" for a bare-minimum container, likely because this is a real
  Python/FastAPI/uvicorn image with a genuine dependency set, not a hello-world binary.
  Render's free plan takes ~30-60s by comparison — still notably slower, so the choice
  still stands, but 14s isn't nothing either; don't undersell it as near-instant. Neither
  is the app being slow, it's the platform starting a fresh container.
- **CORS**: the frontend never calls the agent directly from the browser —
  every request is proxied through Next.js API routes (`web/app/api/agent/[...path]`),
  which forward the session cookie as a Bearer token server-side. No CORS
  configuration is needed on the agent.
- **Vercel function timeout**: that same proxy route sets `export const maxDuration = 60`
  because `POST /deadline-agent`'s Claude-enhanced pass takes ~30-45s, longer than
  Vercel's serverless default (10s on Hobby). Already handled in the code — nothing to
  configure — but worth knowing if you ever see that call fail only in production and not
  locally/on Render, where there's no such limit.
- **Auth**: every estate-scoped endpoint requires a session and ownership, no exceptions —
  "Try the demo" is automated, not unauthenticated: it mints a real session on a fresh,
  independent copy of the seed estate for that visitor only, so no registration form is
  needed but every visitor still owns their own isolated estate. See `agent/api/deps.py`
  and `agent/api/routers/auth.py`'s `demo_login()`. The one true exception is the canonical
  `demo-milligan` record itself, which stays world-readable for `/seed`-based testing.

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
