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
3. Build and push (repo root as build context, `agent/Dockerfile` as the Dockerfile path).
   **`--platform linux/amd64` is not optional on Apple Silicon** — building without it
   produces an ARM64 image, which Cloud Run rejects outright at deploy time with
   `Container manifest type ... must support amd64/linux` (hit this live deploying this
   exact app; confirmed the fix by rebuilding and redeploying successfully):
   ```bash
   docker build --platform linux/amd64 -f agent/Dockerfile \
     -t us-west1-docker.pkg.dev/your-project-id/probatepilot/agent:latest .
   docker push us-west1-docker.pkg.dev/your-project-id/probatepilot/agent:latest
   ```
4. Deploy it, including the secret env vars. Reading them from your local `agent/.env` via
   shell substitution (rather than typing literal values into the command) keeps them out
   of this command's own text, though they still land in `gcloud`'s local command history
   and Cloud Run's revision config either way:
   ```bash
   cd agent
   ANTHROPIC_KEY=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d= -f2-)
   OPENAI_KEY=$(grep "^OPENAI_API_KEY=" .env | cut -d= -f2-)
   REDIS_URL_VAL=$(grep "^REDIS_URL=" .env | cut -d= -f2-)

   gcloud run deploy probatepilot-agent \
     --image us-west1-docker.pkg.dev/your-project-id/probatepilot/agent:latest \
     --region us-west1 --allow-unauthenticated \
     --set-env-vars "STORE_BACKEND=redis_cloud,ANTHROPIC_API_KEY=${ANTHROPIC_KEY},OPENAI_API_KEY=${OPENAI_KEY},REDIS_URL=${REDIS_URL_VAL}"
   ```
   Prefer the Cloud Console instead (Cloud Run service → **Edit & Deploy New Revision** →
   **Variables & Secrets**) if you'd rather not have secrets pass through the CLI at all.
   For real secret hygiene beyond either of these, Cloud Run integrates with Secret Manager
   (`--set-secrets` instead of `--set-env-vars`) — worth doing if you want to go further,
   not required to get this running.
5. Once live, note the service URL (`https://probatepilot-agent-xxxx-uw.a.run.app`).
   Confirm it's healthy: `curl https://<your-service>.run.app/health`.

**Verified against a live GCP account and a real deployed service** (not just written and
assumed): project creation, billing linking, API enablement, the Artifact Registry push,
the `--platform linux/amd64` fix, the deploy itself, and a real request round-tripping
through Redis Cloud all confirmed working end to end — including a measured 13.99s cold
start after 12 minutes idle. `gcloud` CLI flags and free-tier terms can still shift over
time after this was written; cross-check against
[Cloud Run's own quickstart](https://cloud.google.com/run/docs/quickstarts) if a command
ever stops behaving as written.

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

**Dashboard path:**

1. In [Vercel](https://vercel.com/new), import the same fork with **Root
   Directory** set to `web/`.
2. Set the one required env var:
   - `AGENT_API_URL` = the agent's service URL from step 1 (Cloud Run or Render)
3. Optional env vars (voice and error tracking degrade cleanly without them):
   `DEEPGRAM_API_KEY`, `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_DSN`, `SENTRY_ORG`,
   `SENTRY_PROJECT`, `NEXT_PUBLIC_APP_URL` (your Vercel URL, used for
   metadata/share links).
4. Deploy. Vercel auto-detects Next.js — no build config needed.

**CLI path** (what this app's own deploy actually used — verified working):

```bash
npm install -g vercel
vercel login   # opens a device-code flow, confirm in browser

cd web
vercel link --yes --project probatepilot   # one-time; omitting --project auto-names
                                            # it after the directory ("web"), worth
                                            # avoiding for a cleaner project name
vercel env add AGENT_API_URL production      # paste the agent's URL when prompted
vercel env add DEEPGRAM_API_KEY production   # optional, paste your key when prompted

vercel --prod --yes   # deploy; re-run this after any web/ code change
```

## 3. Seed the demo estate

The live app is empty until the demo estate exists. Either:

- Click **Try the demo** on the deployed `/welcome` page (this calls
  `POST /auth/demo` on the agent, which seeds it on first use), or
- Seed it directly: `curl -X POST https://<your-agent-url>/seed`

## 4. Auto-deploy on push (optional)

Both platforms can redeploy automatically on every push to `main`, instead of you re-running
the manual commands above. Neither is wired up by the steps in sections 1-2 alone — both
need one extra one-time setup pass, documented here exactly as it was actually done
end-to-end for this app, gotchas included.

### Cloud Run: a Cloud Build trigger

1. Enable the APIs: `gcloud services enable cloudbuild.googleapis.com
   secretmanager.googleapis.com`
2. Connect GitHub to Cloud Build (one-time OAuth):
   ```bash
   gcloud builds connections create github probatepilot-github --region=us-west1
   ```
   This will likely fail the first time with a Secret Manager permission error — Cloud
   Build's own service agent needs a role granted before it can store the resulting OAuth
   token:
   ```bash
   gcloud projects add-iam-policy-binding <PROJECT_ID> \
     --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-cloudbuild.iam.gserviceaccount.com" \
     --role="roles/secretmanager.admin"
   ```
   Re-run the `connections create` command after granting it; it'll print a URL to open in a
   browser to authorize.
3. Link the specific repo to that connection:
   ```bash
   gcloud builds repositories create probatepilot-repo \
     --connection=probatepilot-github --region=us-west1 \
     --remote-uri="https://github.com/<you>/probatepilot.git"
   ```
4. Create a dedicated service account for the trigger to run as (cleaner than reusing the
   legacy default Cloud Build service account, which has broad `Editor`-level access by
   default):
   ```bash
   gcloud iam service-accounts create probatepilot-deploy \
     --display-name="ProbatePilot Cloud Build Deploy"
   for role in roles/run.admin roles/iam.serviceAccountUser \
               roles/artifactregistry.writer roles/logging.logWriter; do
     gcloud projects add-iam-policy-binding <PROJECT_ID> \
       --member="serviceAccount:probatepilot-deploy@<PROJECT_ID>.iam.gserviceaccount.com" \
       --role="$role"
   done
   ```
5. `cloudbuild.yaml` (repo root) defines the actual build: `docker build -f agent/Dockerfile`
   → push to Artifact Registry → `gcloud run deploy`. Deliberately has **no
   `--platform linux/amd64` flag** despite that being required for the manual local build
   earlier — Cloud Build's own workers run on `linux/amd64` natively, confirmed by the first
   real trigger run succeeding without it. It also has **no `--set-env-vars`** in the deploy
   step, deliberately: `gcloud run deploy` bases a new revision on the currently-serving
   revision's config and only overrides what's explicitly passed, so the secrets set once
   manually when the service was first created carry forward automatically — verified after
   the first automated deploy by checking the new revision still had all four env vars set.
   This also means no secret ever needs to live in this file, which is committed and public.
6. Create the trigger. **The CLI version of this command
   (`gcloud builds triggers create github --repository=... --branch-pattern=... `) returned
   an opaque `INVALID_ARGUMENT` with no further detail** when this was actually done — root
   cause was never fully isolated. The GCP Console GUI flow (**Cloud Build → Triggers →
   Create Trigger**) worked on the first attempt with equivalent settings: Event = Push to a
   branch, Repository service = Cloud Build repositories, Repository generation = 2nd gen,
   Repository = your repo, Branch = `^main$` (Invert regex: off), Configuration = Cloud
   Build configuration file at `cloudbuild.yaml`, Region = matching the connection's region,
   Service account = the dedicated one from step 4, "Send build logs to GitHub" = on (safe —
   the build never handles secrets), "Require approval before build executes" = off (this is
   the actual auto-deploy switch; leaving it on means every push still needs a manual click).
   If the GUI repository picker doesn't find your repo, or the CLI trigger creation fails
   with the same opaque error: check **github.com/settings/installations** → "Google Cloud
   Build" → **Configure** → confirm the correct repo is actually selected (a GitHub App
   installation can silently be scoped to a *different* repository than the one you meant,
   including one with a similar name).
7. Test it without waiting for a real push: `gcloud builds triggers run
   probatepilot-agent-deploy --branch=main --region=us-west1`, then confirm with
   `gcloud run revisions list --service=probatepilot-agent --region=us-west1` that a new
   revision landed.
8. **Scope it to `agent/` changes only** — without this, the trigger fires on *every* push to
   `main`, including `web/`-only commits, wastefully rebuilding and redeploying an unchanged
   agent. Set an Included Files filter to `agent/**` and `cloudbuild.yaml` (so changes to the
   build config itself still trigger a rebuild); leave Ignored Files empty; the CLI
   equivalent (`gcloud builds triggers update github ... --included-files=...`) hit the same
   opaque `INVALID_ARGUMENT` as trigger creation for this app, so this one was also done via
   the Console GUI (trigger → **Edit** → Included files filter, under Advanced). Verify with
   `gcloud builds triggers describe probatepilot-agent-deploy --region=us-west1
   --format="yaml(includedFiles,ignoredFiles)"`.

### Vercel: connect the Git repository

The CLI path (`vercel git connect <repo-url>`) needs GitHub linked as a **login connection**
on your Vercel account first (Account Settings → Login Connections) — without it, the
command fails with "You need to add a Login Connection to your GitHub account first."

Simplest in practice: use the Vercel **dashboard** instead — Project → Settings → **Git** →
connect the repository directly there. If it fails with something like "Make sure ... you
have access to the repository," the same GitHub-App-scoping issue as Cloud Build applies:
check **github.com/apps/vercel** → confirm the repo is actually included in what the app can
access (note: "Authorized" and "Installed" are different things on GitHub — an OAuth
authorization alone isn't enough, the App itself has to be installed with access to the
specific repo).

**Important gotcha if this repo was originally linked via CLI from inside `web/`** (as this
one was, before the dashboard connection): connecting via the dashboard operates from the
repository root and sets **Root Directory = `web`** *relative to that root* in the project's
settings. If you then try to redeploy via CLI from inside `web/` itself, Vercel appends the
configured Root Directory to your current directory and looks for a nonexistent `web/web/`,
failing with "The provided path ... does not exist." Fix: re-link from the **repo root**
instead (`cd` to the repo root, `vercel link --yes --project <name>` — it links to the
existing project rather than creating a duplicate), and remove the now-stale `.vercel/`
folder from inside `web/` so a future `vercel` invocation from there doesn't hit the same
bug again.

Also worth setting once connected: Project Settings → General → **Node.js Version** to match
`web/.nvmrc` (this app pins `20`, not whatever Vercel's project default happens to be), and
**"Skip deployments when there are no changes to the root directory or its dependencies"** —
on, since most commits to this repo touch `agent/` only and shouldn't trigger a frontend
rebuild at all. Settings changes here only apply to the *next* deployment, not retroactively
— redeploy once after changing them to confirm (`vercel --prod --yes` from the repo root) if
you want to verify immediately rather than wait for the next real push.

## Notes

- **Redis Cloud free-tier inactivity reclaim**: per Redis Cloud's own SLA/AUP, a
  Free/Evaluation database is deleted after **14 consecutive days with no read or write
  commands** — logging into the console or viewing metrics doesn't count as activity, and
  email warnings before deletion aren't guaranteed to arrive. A portfolio deploy with
  sporadic visitor traffic can easily go 14 days idle. Mitigated with a Cloud Scheduler job
  (`probatepilot-redis-keepalive`, weekly, `POST /seed`) that guarantees a real write at
  least once a week regardless of visitor traffic:
  ```bash
  gcloud scheduler jobs create http probatepilot-redis-keepalive \
    --location=us-west1 --schedule="0 9 * * 1" \
    --uri="https://<your-agent>.run.app/seed" --http-method=POST \
    --time-zone="America/Los_Angeles"
  ```
  `/seed` also runs a real DeadlineAgent Claude call each time (not just a Redis touch), so
  this is a small real recurring cost (~$0.01-0.07/week based on this app's own measured
  DeadlineAgent trace costs), not a free no-op.
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
