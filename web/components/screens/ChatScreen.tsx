"use client";

// Estate chat — design from the prototype, wired to the real agent (SSE streaming)
// and real Deepgram voice (hold-to-speak STT + spoken replies for voice turns).
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Avatar, Button } from "@/components/ds";
import type { EstateProfile } from "@/lib/design/data";
import { getEstate, openChatStream } from "@/lib/agentClient";

const I = ExecutorIcons;

type Props = { estate: EstateProfile };

type Msg = { from: "ai" | "user"; text: string };

const SUGGESTIONS = ["What's the most urgent deadline?", "How much does the estate owe?", "Explain a DE-160 in plain English"];

function firstName(full: string): string {
  return full.trim().split(/\s+/)[0] || full.trim();
}

function humanList(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

// Build the opening message from the real estate: who the executor is, who died,
// and which documents have actually been parsed.
function buildGreeting(deceasedName: string, executorName?: string | null, documentTypes: string[] = []): string {
  const hello = executorName ? `Hi ${firstName(executorName)}, ` : "Hi there, ";
  const tail = `Ask me anything about ${firstName(deceasedName)}'s estate, or I can tell you the most urgent thing to handle.`;
  if (documentTypes.length === 0) return `${hello}${tail}`;
  const docs = humanList(documentTypes.map((t) => t.replace(/_/g, " ")));
  return `${hello}I've read ${docs}. ${tail}`;
}

export function ChatScreen({ estate }: Props) {
  const suggestions = SUGGESTIONS;
  const [msgs, setMsgs] = React.useState<Msg[]>(() => [{ from: "ai", text: buildGreeting(estate.deceasedName) }]);
  const [subtitle, setSubtitle] = React.useState(`Grounded in ${firstName(estate.deceasedName)}'s documents, not legal advice`);
  const [draft, setDraft] = React.useState("");
  const [recording, setRecording] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const endRef = React.useRef<HTMLDivElement>(null);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);

  // Enrich the greeting once the real estate loads — but only if the executor
  // hasn't started the conversation yet.
  React.useEffect(() => {
    if (!estate.id) return;
    let cancelled = false;
    getEstate(estate.id)
      .then((e) => {
        if (cancelled) return;
        setSubtitle(`Grounded in ${firstName(e.deceasedName)}'s documents, not legal advice`);
        const greeting = buildGreeting(e.deceasedName, e.executor?.name, e.documents.map((d) => d.documentType));
        setMsgs((m) => (m.length === 1 && m[0].from === "ai" ? [{ from: "ai", text: greeting }] : m));
      })
      .catch(() => {
        /* keep the name-only greeting if the estate can't be fetched */
      });
    return () => { cancelled = true; };
  }, [estate.id]);

  React.useEffect(() => {
    if (endRef.current && endRef.current.parentNode) (endRef.current.parentNode as HTMLElement).scrollTop = endRef.current.offsetTop;
  }, [msgs]);

  async function send(text?: string, viaVoice = false) {
    const t = (text ?? draft).trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { from: "user", text: t }, { from: "ai", text: "" }]);
    setDraft("");
    setBusy(true);

    let full = "";
    try {
      const stream = await openChatStream({ estateId: estate.id, message: t });
      const reader = stream?.getReader();
      const decoder = new TextDecoder();
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ") || line.includes("[DONE]")) continue;
            const parsed = JSON.parse(line.replace("data: ", ""));
            full += parsed.token ?? "";
            setMsgs((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { from: "ai", text: full };
              return copy;
            });
          }
        }
      }
      if (viaVoice && full.trim()) void speak(full);
    } catch {
      setMsgs((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { from: "ai", text: "I couldn't reach the estate service. Make sure the agent is running on :8000, then try again." };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  // ── Deepgram voice: hold the mic to record, release to transcribe & send ──
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        await transcribe(blob);
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (err) {
      console.error(err);
    }
  }

  function stopRecording() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    setRecording(false);
  }

  async function transcribe(blob: Blob) {
    try {
      const res = await fetch("/api/voice/transcribe", { method: "POST", headers: { "content-type": blob.type || "audio/webm" }, body: blob });
      if (!res.ok) throw new Error(`transcribe ${res.status}`);
      const { transcript } = await res.json();
      if (transcript) void send(transcript, true);
    } catch (err) {
      console.error(err);
    }
  }

  async function speak(text: string) {
    try {
      const res = await fetch("/api/voice/speak", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) });
      if (!res.ok) return;
      const buf = await res.arrayBuffer();
      const url = URL.createObjectURL(new Blob([buf], { type: "audio/mpeg" }));
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      void audio.play();
    } catch (err) {
      console.error(err);
    }
  }

  if (estate && !estate.hasDocuments) {
    return (
      <div style={{ maxWidth: 560, margin: "0 auto", padding: "80px 40px", textAlign: "center" }}>
        <span style={{ display: "inline-flex", width: 52, height: 52, borderRadius: "999px", background: "var(--evergreen-100)", color: "var(--evergreen-700)", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
          <I.Chat size={24} />
        </span>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>Chat opens once there are documents</h1>
        <p style={{ margin: "10px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)" }}>
          Add a will, deed, or statement to the estate of {estate.deceasedName} and I&apos;ll answer your questions grounded in those documents, never generic advice.
        </p>
      </div>
    );
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", maxWidth: 760, margin: "0 auto", width: "100%" }}>
      <header style={{ padding: "24px 28px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--text-strong)" }}>Estate chat</h1>
        <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{subtitle}</p>
      </header>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", flexDirection: m.from === "user" ? "row-reverse" : "row" }}>
            {m.from === "ai" ? <Avatar initials="AI" tone="ink" size="sm" /> : <Avatar name="Dana Milligan" size="sm" />}
            <div style={{
              maxWidth: "76%", whiteSpace: "pre-wrap", lineHeight: "var(--leading-relaxed)", fontSize: "var(--text-base)",
              padding: "12px 16px", borderRadius: m.from === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              background: m.from === "user" ? "var(--evergreen-700)" : "var(--surface-card)",
              color: m.from === "user" ? "var(--text-inverse)" : "var(--text-body)",
              border: m.from === "user" ? "none" : "1px solid var(--border-subtle)",
              boxShadow: "var(--shadow-xs)",
            }}>{m.text || (m.from === "ai" && busy ? "…" : "")}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div style={{ padding: "12px 28px 24px", borderTop: "1px solid var(--border-subtle)", background: "var(--paper-50)" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          {suggestions.map((s) => (
            <button key={s} onClick={() => send(s)} style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", color: "var(--text-brand)", background: "var(--evergreen-50)", border: "1px solid var(--evergreen-200)", borderRadius: "var(--radius-full)", padding: "6px 12px", cursor: "pointer" }}>{s}</button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
          <button
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onMouseLeave={() => recording && stopRecording()}
            onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
            onTouchEnd={(e) => { e.preventDefault(); stopRecording(); }}
            aria-label="Hold to speak"
            style={{ width: 44, height: 44, flex: "none", borderRadius: "var(--radius-md)", cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center",
              background: recording ? "var(--evergreen-700)" : "var(--surface-card)", color: recording ? "var(--text-inverse)" : "var(--text-muted)",
              border: recording ? "1px solid var(--evergreen-700)" : "1px solid var(--border-default)", transition: "all var(--transition-fast)" }}>
            <I.Mic size={20} />
          </button>
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={1}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder={recording ? "Listening…" : "Ask about this estate"}
            style={{ flex: 1, resize: "none", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)", lineHeight: 1.5, color: "var(--text-body)",
              background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "11px 14px", outline: "none", minHeight: 44, boxSizing: "border-box" }} />
          <Button variant="primary" onClick={() => send()} disabled={busy} leadingIcon={<I.Send size={16} />} style={{ height: 44 }}>Send</Button>
        </div>
      </div>
    </div>
  );
}
