# Member 4 — Frontend + Chat + Voice

**Owner**: TBD  
**Track dependency**: You build what judges see. The dashboard, chat interface, and voice are the demo. Also owns the RAG chat API — which is the first thing that becomes demo-worthy.

---

## Your Mission

You own everything the user sees and touches, plus the backend that powers the chat. This means the dashboard (estate overview + alert banners), the chat interface with streaming responses, Deepgram voice integration, and the document upload UI. You also own the RAG chat API route — the most complex backend endpoint after DeadlineAgent.

---

## Files You Own

```
lib/
├── deepgram.ts                      ← Deepgram client + STT/TTS helpers

app/
├── layout.tsx                       ← Root layout, global styles
├── page.tsx                         ← Dashboard: estate overview + alert banners + task list
├── chat/
│   └── page.tsx                     ← Chat interface page
├── upload/
│   └── page.tsx                     ← Document upload page
└── api/
    ├── chat/
    │   └── route.ts                 ← POST: RAG → Claude streaming → response
    └── voice/
        ├── transcribe/
        │   └── route.ts             ← POST: audio → Deepgram STT → text
        └── speak/
            └── route.ts             ← POST: text → Deepgram TTS → audio

components/
├── EstateOverview.tsx               ← Summary: total assets, debts, days to next deadline
├── AlertBanner.tsx                  ← Red/yellow/blue alert cards — THE HERO COMPONENT
├── ChatInterface.tsx                ← Streaming chat with voice toggle
├── DocumentUpload.tsx               ← Drag-and-drop upload with parsing progress
├── TaskList.tsx                     ← Phase-gated checklist of next steps
├── LetterPreview.tsx                ← Draft letter with copy/edit/regenerate
└── VoiceButton.tsx                  ← Hold-to-speak button, Deepgram integration
```

---

## Build Order

### Phase 1 — RAG Chat API (Hour 0–3)
Build the chat backend first — it's the first demo-worthy moment. Everything else is polish.

```typescript
// app/api/chat/route.ts
import { NextRequest } from "next/server"
import { getEstateState, searchVectors } from "@/lib/redis"
import { embedChunks } from "@/lib/embeddings"
import { streamChat } from "@/lib/claude"
import { buildSystemPrompt } from "@/lib/prompts/system-prompt"
import { withSentryTransaction } from "@/lib/sentry"

export async function POST(req: NextRequest) {
  const { message, estateId = "demo-milligan" } = await req.json()

  // Embed the query to search Redis vector index
  const [queryEmbedding] = await embedChunks([message])

  // RAG: retrieve top 5 relevant document chunks
  const retrievedChunks = await searchVectors(estateId, queryEmbedding, 5)

  // Load estate state
  const state = await getEstateState(estateId)
  if (!state) return new Response("Estate not found", { status: 404 })

  // Build system prompt with estate context + retrieved chunks
  const systemPrompt = buildSystemPrompt(state, retrievedChunks)

  // Stream Claude response
  return withSentryTransaction(
    "chat_query",
    { estate_id: estateId, action_type: "chat_query" },
    async () => {
      const stream = streamChat(
        [{ role: "user", content: message }],
        systemPrompt
      )

      // Return as a streaming response compatible with Vercel AI SDK
      return stream.toReadableStream()
    }
  )
}
```

> Note: `streamChat()` is from `lib/claude.ts` (Member 1). `buildSystemPrompt()` is from `lib/prompts/system-prompt.ts` (Member 3). `searchVectors()` and `getEstateState()` are from `lib/redis.ts` (Member 2).

### Phase 2 — Dashboard Page (Hour 3–5)

The dashboard (`app/page.tsx`) is the first screen judges see. It must show:
1. Estate summary (who died, executor name, appointment date)
2. Alert banners — sorted critical first, red/yellow/blue
3. Task checklist
4. Quick-action buttons (Upload Document, Open Chat, Generate Letter)

```typescript
// app/page.tsx — Server Component (fetches estate + alerts on load)
import { getEstateState } from "@/lib/redis"
import { runDeadlineAgent } from "@/lib/agents/deadline-agent"
import EstateOverview from "@/components/EstateOverview"
import AlertBanner from "@/components/AlertBanner"
import TaskList from "@/components/TaskList"

export default async function DashboardPage() {
  const estateId = "demo-milligan"
  const state = await getEstateState(estateId)
  const alerts = await runDeadlineAgent(estateId)   // Refresh on every load for demo

  if (!state) return <div>No estate found. <a href="/api/seed">Seed demo data</a></div>

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <EstateOverview state={state} />
      <div className="space-y-3">
        {alerts.map(alert => <AlertBanner key={alert.id} alert={alert} />)}
      </div>
      <TaskList tasks={state.tasks} phase={state.phase} />
    </main>
  )
}
```

**AlertBanner** is the hero component — make it visually striking:

```typescript
// components/AlertBanner.tsx
import type { Alert } from "@/types/alerts"

const SEVERITY_STYLES = {
  critical: "border-l-4 border-red-500 bg-red-50 text-red-900",
  warning: "border-l-4 border-yellow-500 bg-yellow-50 text-yellow-900",
  info: "border-l-4 border-blue-500 bg-blue-50 text-blue-900",
}

export default function AlertBanner({ alert }: { alert: Alert }) {
  return (
    <div className={`p-4 rounded-md ${SEVERITY_STYLES[alert.severity]}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold text-sm uppercase tracking-wide">
            {alert.severity === "critical" ? "⚠ URGENT" : alert.severity === "warning" ? "Warning" : "Info"}
            {alert.daysRemaining !== undefined && ` — ${alert.daysRemaining} days`}
          </p>
          <h3 className="font-bold text-lg mt-1">{alert.title}</h3>
          <p className="mt-1 text-sm">{alert.body}</p>
        </div>
      </div>
      <div className="mt-3 p-2 bg-white/60 rounded text-sm font-medium">
        Next action: {alert.actionRequired}
      </div>
    </div>
  )
}
```

### Phase 3 — Chat Interface (Hour 5–7)

```typescript
// app/chat/page.tsx
"use client"
import { useState, useRef } from "react"
import ChatInterface from "@/components/ChatInterface"

export default function ChatPage() {
  return <ChatInterface estateId="demo-milligan" />
}
```

```typescript
// components/ChatInterface.tsx
"use client"
import { useState } from "react"
import VoiceButton from "./VoiceButton"

interface Message {
  role: "user" | "assistant"
  content: string
}

export default function ChatInterface({ estateId }: { estateId: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [voiceMode, setVoiceMode] = useState(false)

  async function sendMessage(text: string) {
    const userMessage = { role: "user" as const, content: text }
    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, estateId }),
    })

    // Handle streaming response
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let assistantText = ""

    setMessages(prev => [...prev, { role: "assistant", content: "" }])

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      assistantText += decoder.decode(value, { stream: true })
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: "assistant", content: assistantText }
      ])
    }

    setIsLoading(false)

    // If voice mode, read the response aloud
    if (voiceMode) {
      await speakText(assistantText)
    }
  }

  async function speakText(text: string) {
    const res = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
    const audio = new Audio(URL.createObjectURL(await res.blob()))
    audio.play()
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto p-4">
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg text-sm ${
              msg.role === "user"
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-900"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && <div className="text-gray-400 text-sm">Thinking...</div>}
      </div>
      <div className="flex gap-2 items-center pt-2 border-t">
        <input
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && sendMessage(input)}
          placeholder="Ask about the estate..."
        />
        <VoiceButton onTranscription={sendMessage} />
        <button
          className={`px-3 py-2 rounded-lg text-sm ${voiceMode ? "bg-blue-600 text-white" : "bg-gray-100"}`}
          onClick={() => setVoiceMode(!voiceMode)}
        >
          {voiceMode ? "Voice On" : "Voice Off"}
        </button>
        <button
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm"
          onClick={() => sendMessage(input)}
        >
          Send
        </button>
      </div>
    </div>
  )
}
```

### Phase 4 — Deepgram Voice (Hour 7–10)

```typescript
// lib/deepgram.ts
import { createClient } from "@deepgram/sdk"

export const deepgram = createClient(process.env.DEEPGRAM_API_KEY!)

export async function transcribeAudio(audioBuffer: Buffer, mimetype: string): Promise<string> {
  const { result, error } = await deepgram.listen.prerecorded.transcribeFile(
    audioBuffer,
    { model: "nova-3", smart_format: true, mimetype }
  )
  if (error) throw error
  return result?.results?.channels?.[0]?.alternatives?.[0]?.transcript ?? ""
}

export async function synthesizeSpeech(text: string): Promise<Buffer> {
  const response = await deepgram.speak.request(
    { text },
    { model: "aura-asteria-en" }
  )
  const stream = await response.getStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream) {
    chunks.push(Buffer.from(chunk))
  }
  return Buffer.concat(chunks)
}
```

```typescript
// app/api/voice/transcribe/route.ts
import { NextRequest, NextResponse } from "next/server"
import { transcribeAudio } from "@/lib/deepgram"

export async function POST(req: NextRequest) {
  const formData = await req.formData()
  const file = formData.get("audio") as File
  const buffer = Buffer.from(await file.arrayBuffer())
  const transcript = await transcribeAudio(buffer, file.type)
  return NextResponse.json({ transcript })
}

// app/api/voice/speak/route.ts
export async function POST(req: NextRequest) {
  const { text } = await req.json()
  const audioBuffer = await synthesizeSpeech(text)
  return new Response(audioBuffer, {
    headers: { "Content-Type": "audio/mpeg" }
  })
}
```

```typescript
// components/VoiceButton.tsx
"use client"
import { useState, useRef } from "react"

export default function VoiceButton({ onTranscription }: { onTranscription: (text: string) => void }) {
  const [isRecording, setIsRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mediaRecorder = new MediaRecorder(stream)
    mediaRecorderRef.current = mediaRecorder
    chunksRef.current = []

    mediaRecorder.ondataavailable = e => chunksRef.current.push(e.data)
    mediaRecorder.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" })
      const formData = new FormData()
      formData.append("audio", blob, "recording.webm")
      const res = await fetch("/api/voice/transcribe", { method: "POST", body: formData })
      const { transcript } = await res.json()
      if (transcript) onTranscription(transcript)
    }

    mediaRecorder.start()
    setIsRecording(true)
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  return (
    <button
      className={`w-10 h-10 rounded-full flex items-center justify-center ${
        isRecording ? "bg-red-500 animate-pulse" : "bg-gray-200"
      }`}
      onMouseDown={startRecording}
      onMouseUp={stopRecording}
      onTouchStart={startRecording}
      onTouchEnd={stopRecording}
    >
      {isRecording ? "●" : "🎤"}
    </button>
  )
}
```

### Phase 5 — Document Upload UI (Hour 10–12)

```typescript
// components/DocumentUpload.tsx
"use client"
import { useState, useCallback } from "react"

export default function DocumentUpload({ estateId }: { estateId: string }) {
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [result, setResult] = useState<any>(null)

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (!file) return

    setStatus("uploading")
    const formData = new FormData()
    formData.append("file", file)
    formData.append("estateId", estateId)

    try {
      const res = await fetch("/api/parse-document", { method: "POST", body: formData })
      const data = await res.json()
      setResult(data)
      setStatus("done")
    } catch {
      setStatus("error")
    }
  }, [estateId])

  return (
    <div
      onDrop={handleDrop}
      onDragOver={e => e.preventDefault()}
      className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center cursor-pointer hover:border-blue-400 transition"
    >
      {status === "idle" && (
        <div>
          <p className="text-2xl mb-2">📄</p>
          <p className="font-medium">Drop a document here</p>
          <p className="text-sm text-gray-500 mt-1">Will, bank statement, deed, or insurance policy</p>
        </div>
      )}
      {status === "uploading" && <p className="text-blue-600">Parsing document with AI...</p>}
      {status === "done" && (
        <div className="text-left">
          <p className="text-green-600 font-semibold mb-2">Document parsed successfully</p>
          <pre className="text-xs bg-gray-100 p-3 rounded overflow-auto max-h-40">
            {JSON.stringify(result?.extraction, null, 2)}
          </pre>
        </div>
      )}
      {status === "error" && <p className="text-red-600">Failed to parse document. Try again.</p>}
    </div>
  )
}
```

### Phase 6 — Remaining Components (Hour 12–15)

**EstateOverview.tsx** — Summary bar at top of dashboard:
- Total asset value (sum of estimatedValue)
- Total debt
- Days until next critical deadline
- Estate phase badge

**TaskList.tsx** — Phase-gated task checklist:
- Pull `tasks` from estate state
- Group by phase, show current phase's tasks as active
- Checkboxes call `PATCH /api/estate/task` to toggle completion

**LetterPreview.tsx** — Rendered letter with actions:
- Calls `POST /api/generate-letter` on mount with letter type
- Shows formatted letter text
- "Copy to clipboard" and "Regenerate" buttons

---

## Coordination Points

| You need from... | What |
|-----------------|------|
| **Member 1** | `streamChat()` from `lib/claude.ts` — used in chat API route |
| **Member 2** | `getEstateState()`, `searchVectors()` from `lib/redis.ts` |
| **Member 2** | `EstateState`, `Alert`, `Task` types from `types/` |
| **Member 3** | `buildSystemPrompt()` from `lib/prompts/system-prompt.ts` |
| **Member 3** | `withSentryTransaction()` from `lib/sentry.ts` |
| **Member 3** | `GET /api/deadline-agent` — call after upload to refresh dashboard alerts |

| Others need from you | What |
|--------------------|------|
| Everyone | Working UI to demonstrate the product during the demo |

---

## Acceptance Criteria

- [ ] Dashboard loads with estate overview, 2 critical alerts visible for demo-milligan
- [ ] Chat sends a message and receives a streaming response grounded in estate data
- [ ] VoiceButton records audio, sends to Deepgram, transcription appears in chat input
- [ ] Voice mode reads Claude's response aloud via Deepgram TTS
- [ ] Document upload accepts a PDF drop, shows parsing progress, updates dashboard on complete
- [ ] LetterPreview generates a creditor notice letter with correct names/dates filled in
- [ ] Mobile-readable layout (executors use this on their phones)

---

## Demo Script (What to Show Judges)

1. **Open dashboard** — Two red critical alerts are visible immediately. "DE-160 filing due in 9 days. No appraisal uploaded." Judges see the proactive intelligence before you say a word.
2. **Open chat** — Ask: *"What happens if I miss the DE-160 deadline?"* Claude responds with specific dates, the exact statute, and Dana's personal liability.
3. **Voice** — Hold the mic button. Ask: *"What do I need to do this week?"* Claude responds. Tap voice mode — it reads the answer aloud.
4. **Upload** — Drop the will PDF. Parsing indicator. Estate state updates. A new task appears in the task list.
5. **Generate letter** — Click "Notify creditors." Show the UCSF Medical Center letter with Robert Milligan's name, dates, and Case No. pre-filled.

---

## Sponsor Requirements You Unlock

- **Deepgram track**: Voice is demonstrably essential — the executor uses it during phone calls with banks and institutions (hands-free, reading Claude's script back). Show STT transcription AND TTS playback in the demo.
- **Anthropic track**: The streaming chat with RAG shows Claude reasoning over specific estate documents, not generic advice.
- **Redis track**: Every chat query runs a Redis Iris vector search — make sure retrieved chunks appear visually (a "Sources" section under the response is a nice touch for judges).
