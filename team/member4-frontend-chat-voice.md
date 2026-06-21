# Member 4 — Frontend + Voice (TypeScript)

**Owner**: Sherry
**Language**: TypeScript (`web/`)
**Track dependency**: You build what the judges see and touch. The dashboard, chat, and
voice *are* the demo. You also own the Deepgram voice integration (a whole prize) and the
Sentry observability on the web layer (another prize).

---

## Your Mission
You own everything the user experiences: the dashboard (estate overview + the hero alert
banners), the streaming chat interface, Deepgram voice, the document-upload UI, and letter
preview. You consume the Python agent through one thin, typed, Sentry-wrapped client — you
do **not** reimplement any AI logic. Your job is to make the agent's intelligence feel
immediate, calm, and trustworthy to a grieving person.

---

## What You Own
```
web/
├── app/
│   ├── page.tsx                     # Dashboard: overview + alert banners + tasks
│   ├── chat/page.tsx                # Chat page
│   ├── upload/page.tsx              # Upload page
│   └── api/
│       ├── agent/[...path]/route.ts # Sentry-wrapped proxy to the Python service
│       └── voice/
│           ├── transcribe/route.ts  # Audio → Deepgram STT → text
│           └── speak/route.ts       # Text → Deepgram TTS → audio
├── components/
│   ├── EstateOverview.tsx           # Asset/debt totals, next-deadline countdown, phase
│   ├── AlertBanner.tsx              # THE HERO COMPONENT — critical/warning/info cards
│   ├── ChatInterface.tsx            # Streaming chat with a voice toggle
│   ├── DocumentUpload.tsx           # Drag-and-drop with parsing status
│   ├── TaskList.tsx                 # Phase-gated checklist
│   ├── LetterPreview.tsx            # Generated letter with copy / regenerate
│   └── VoiceButton.tsx              # Hold-to-speak (Deepgram)
└── lib/
    ├── agentClient.ts               # Typed fetch wrapper over the Python service
    ├── deepgram.ts                  # Deepgram client + STT/TTS helpers
    └── sentry.ts                    # Sentry init + span helper
```

---

## How To Approach It

### The agent client + proxy (`web/lib/agentClient.ts`, `app/api/agent/...`)
All AI lives in the Python service. The browser never calls it directly. Build:
- a **typed client** that calls the agent's endpoints (parse, chat, deadline-agent,
  generate-letter, seed) using Member 2's shared TS types,
- a **Next.js route handler that proxies** to the Python service, wrapped in a Sentry span
  so every agent interaction is observable from the web side. The chat endpoint streams
  (SSE) — make sure the proxy passes the stream through to the browser, token by token.

### Dashboard (`app/page.tsx`) — first screen the judges see
On load, fetch estate state and run the DeadlineAgent (refresh alerts every load for the
demo). Show: estate summary (who died, executor, appointment date), **alert banners sorted
critical-first**, the task checklist, and quick actions (Upload, Chat, Generate Letter).

**AlertBanner is the hero.** Make it visually striking and emotionally calm:
critical = red, warning = amber, info = blue; show severity, days-remaining, title, the
plain-English body, and a clearly separated "Next action." This component is the proof that
the product is proactive — judges should understand the whole pitch before you say a word.

### Chat (`app/chat/page.tsx`, `ChatInterface.tsx`)
A streaming chat that posts to the agent (via the proxy) and renders tokens as they arrive.
Include a voice toggle. If Member 2's search results carry source/score, surface a small
"Sources" section under answers — a nice citation touch that reinforces the Redis story.

### Voice (`lib/deepgram.ts`, `app/api/voice/*`, `VoiceButton.tsx`)
- **STT**: hold-to-speak records mic audio, posts it to the transcribe route, which runs
  Deepgram speech-to-text; the transcript becomes the chat input.
- **TTS**: in voice mode, Claude's response text is sent to the speak route (Deepgram
  text-to-speech) and played back.
Frame the use case clearly in the demo: the executor is **on the phone with a bank**,
hands-free, and ClearPath reads them the script and answers questions out loud. That makes
voice essential, not decorative.

### Upload (`DocumentUpload.tsx`) & Letters (`LetterPreview.tsx`)
- Upload: drag-and-drop a PDF → POST to the parse endpoint → show a parsing indicator →
  on success, update the dashboard (new facts, possibly new alerts/tasks).
- Letters: call generate-letter for a chosen type, render the formatted draft, offer copy
  and regenerate.

### Sentry (`lib/sentry.ts`)
Initialize `@sentry/nextjs` (client + server). Wrap the agent proxy and the voice routes in
spans. This is ~30 minutes and it's a prize — get it working early and make sure a real
transaction is visible in the Sentry dashboard during the demo.

---

## Coordination
| You need from… | What |
|----------------|------|
| **Member 2** | Shared TS types + Zod schemas for estate state, alerts, tasks |
| **Member 3** | `POST /chat` (SSE), `POST /deadline-agent`, `POST /generate-letter` |
| **Member 1** | `POST /parse-document` returning `{ extraction, alerts }` |

| Others need from you | What |
|----------------------|------|
| **Everyone** | A working, demo-ready UI that makes the agent's intelligence felt |

---

## Acceptance Criteria
- [ ] Dashboard loads with the estate overview and 2 critical alerts visible for
      `demo-milligan`.
- [ ] Chat sends a message and renders a streaming, estate-grounded response.
- [ ] VoiceButton records audio → Deepgram STT → transcript appears as chat input.
- [ ] Voice mode reads Claude's response aloud via Deepgram TTS.
- [ ] Document upload accepts a PDF drop, shows parsing progress, and refreshes the
      dashboard on completion.
- [ ] LetterPreview generates a creditor-notice letter with the right names and dates.
- [ ] Mobile-readable layout (executors use this on their phones).
- [ ] A real Sentry transaction is visible during the demo.

---

## Demo Script (what to show judges)
1. **Open the dashboard** — two red critical alerts are already there. "DE-160 due in
   9 days, no appraisal uploaded." The proactive intelligence lands before you speak.
2. **Open chat** — ask *"What happens if I miss the DE-160 deadline?"* Claude answers with
   the exact date, the statute, and Dana's personal liability — grounded in her estate.
3. **Voice** — hold the mic: *"What do I need to do this week?"* Claude answers; tap voice
   mode and it reads the answer aloud, as if Dana were on the phone with the bank.
4. **Upload** — drop the will PDF. Parsing indicator. Estate updates. A new task appears.
5. **Generate letter** — click "Notify creditors." Show the UCSF Medical Center letter,
   pre-filled with Robert Milligan's name and the right dates.

---

## Sponsor Hooks You Unlock
- **Deepgram** — voice is demonstrably essential (hands-free during a bank call). Show
  both STT and TTS in the demo.
- **Sentry** — the web layer is observable; show a live transaction and a team that
  course-corrected under pressure.
- **Anthropic / Redis** — the streaming, grounded chat with visible sources shows Claude
  reasoning over *this* estate's documents from Redis, not generic advice.
