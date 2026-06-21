"use client";

// Estate chat — design from the prototype, wired to the real agent (SSE streaming)
// and real Deepgram voice (hold-to-speak STT + spoken replies for voice turns).
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Avatar, Button, Spinner } from "@/components/ds";
import { Markdown } from "@/components/Markdown";
import type { EstateProfile } from "@/lib/design/data";
import { createChatSession, getChatHistory, getChatSessions, getChatSuggestions, getEstate, openChatStream } from "@/lib/agentClient";
import type { ChatSession, EstateState } from "@/types";

const I = ExecutorIcons;

type Props = { estate: EstateProfile };

type Msg = { from: "ai" | "user"; text: string };

// Shown before the real estate loads (or if it can't be fetched).
const DEFAULT_SUGGESTIONS = ["What's the most urgent deadline?", "What should I do next?", "Explain a DE-160 in plain English"];

// Build suggested questions from the actual estate state so they point at this
// estate's real deadlines, debts, and people instead of a fixed script.
function buildSuggestions(estate: EstateState): string[] {
  const out: string[] = [];
  if (estate.alerts?.length) out.push("What's the most urgent deadline?");
  if (estate.debts?.length) {
    out.push("How much does the estate owe?");
    const unnotified = estate.debts.find((d) => !d.notified);
    if (unnotified) out.push(`Do I need to notify ${unnotified.creditor}?`);
  }
  if (estate.assets?.length) out.push("What is the estate worth right now?");
  if (estate.beneficiaries?.length) out.push("Who inherits what under the will?");
  out.push("What should I do next?");
  const unique = Array.from(new Set(out));
  return (unique.length ? unique : DEFAULT_SUGGESTIONS).slice(0, 3);
}

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
  const [suggestions, setSuggestions] = React.useState<string[]>(DEFAULT_SUGGESTIONS);
  const [msgs, setMsgs] = React.useState<Msg[]>(() => [{ from: "ai", text: buildGreeting(estate.deceasedName) }]);
  const [sessions, setSessions] = React.useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  const [subtitle, setSubtitle] = React.useState(`Grounded in ${firstName(estate.deceasedName)}'s documents, not legal advice`);
  const [draft, setDraft] = React.useState("");
  const [recording, setRecording] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  // Covers the brief flash of the placeholder greeting before the real estate
  // and saved history load.
  const [loading, setLoading] = React.useState(true);
  const endRef = React.useRef<HTMLDivElement>(null);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);

  // Load the real estate (for the greeting + suggestions) and any prior chat
  // history. If there's saved history, restore the conversation; otherwise show
  // a greeting built from this estate's executor, deceased, and parsed documents.
  React.useEffect(() => {
    if (!estate.id) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([getEstate(estate.id), getChatSessions(estate.id)]).then(async ([eRes, sRes]) => {
      if (cancelled) return;
      const estateData = eRes.status === "fulfilled" ? eRes.value : null;
      const nextSessions = sRes.status === "fulfilled" ? sRes.value : [];
      if (estateData) {
        setSubtitle(`Grounded in ${firstName(estateData.deceasedName)}'s documents, not legal advice`);
        setSuggestions(buildSuggestions(estateData));
      }
      setSessions(nextSessions);
      const latestSessionId = nextSessions[0]?.id ?? null;
      setActiveSessionId(latestSessionId);
      const history = latestSessionId ? await getChatHistory(estate.id, latestSessionId).catch(() => []) : [];
      if (cancelled) return;
      if (history.length > 0) {
        setMsgs(history.map((m) => ({ from: m.role === "user" ? "user" : "ai", text: m.content })));
      } else if (estateData) {
        const greeting = buildGreeting(estateData.deceasedName, estateData.executor?.name, estateData.documents.map((d) => d.documentType));
        setMsgs((m) => (m.length === 1 && m[0].from === "ai" ? [{ from: "ai", text: greeting }] : m));
      }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [estate.id]);

  const greeting = React.useCallback(() => buildGreeting(estate.deceasedName), [estate.deceasedName]);

  async function refreshSessions(nextActiveId?: string | null) {
    const next = await getChatSessions(estate.id).catch(() => []);
    setSessions(next);
    if (nextActiveId !== undefined) setActiveSessionId(nextActiveId);
  }

  async function openSession(sessionId: string) {
    if (busy || sessionId === activeSessionId) return;
    setActiveSessionId(sessionId);
    const history = await getChatHistory(estate.id, sessionId).catch(() => []);
    setMsgs(history.length ? history.map((m) => ({ from: m.role === "user" ? "user" : "ai", text: m.content })) : [{ from: "ai", text: greeting() }]);
  }

  async function startNewChat() {
    if (busy) return;
    const created = await createChatSession(estate.id).catch(() => null);
    if (!created) {
      setActiveSessionId(null);
      setMsgs([{ from: "ai", text: greeting() }]);
      return;
    }
    setActiveSessionId(created.session.id);
    setSessions((current) => [created.session, ...current.filter((s) => s.id !== created.session.id)]);
    setMsgs([{ from: "ai", text: greeting() }]);
  }

  React.useEffect(() => {
    if (endRef.current && endRef.current.parentNode) (endRef.current.parentNode as HTMLElement).scrollTop = endRef.current.offsetTop;
  }, [msgs]);

  // Pull fresh follow-up suggestions (grounded in the conversation so far). Called
  // after each exchange so the chips reflect what was just discussed.
  async function refreshSuggestions() {
    try {
      const next = await getChatSuggestions(estate.id);
      if (next.length) setSuggestions(next.slice(0, 3));
    } catch {
      /* keep the existing suggestions if the refresh fails */
    }
  }

  async function send(text?: string, viaVoice = false) {
    const t = (text ?? draft).trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { from: "user", text: t }, { from: "ai", text: "" }]);
    setDraft("");
    setBusy(true);

    let full = "";
    let sessionId = activeSessionId;
    try {
      if (!sessionId) {
        const created = await createChatSession(estate.id);
        sessionId = created.session.id;
        setActiveSessionId(sessionId);
        setSessions((current) => [created.session, ...current.filter((s) => s.id !== created.session.id)]);
      }
      const stream = await openChatStream({ estateId: estate.id, sessionId, message: t });
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
            if (parsed.sessionId) {
              sessionId = parsed.sessionId;
              setActiveSessionId(sessionId);
            }
            full += parsed.token ?? "";
            setMsgs((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { from: "ai", text: full };
              return copy;
            });
          }
        }
      }
      await refreshSessions(sessionId);
      if (viaVoice && full.trim()) void speak(full);
      // The exchange is now persisted server-side; regenerate the suggested
      // next questions from the updated conversation.
      void refreshSuggestions();
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

  function sessionLabel(session: ChatSession): string {
    const when = new Date(session.updatedAt);
    return Number.isNaN(when.getTime()) ? "" : when.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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

  if (loading) {
    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 14, color: "var(--text-muted)" }}>
        <Spinner size={26} />
        <p style={{ margin: 0, fontSize: "var(--text-sm)" }}>Opening your estate chat…</p>
      </div>
    );
  }

  return (
    <div style={{ height: "100%", display: "grid", gridTemplateColumns: "240px minmax(0, 1fr)", width: "100%", minWidth: 0 }}>
      <aside style={{ borderRight: "1px solid var(--border-subtle)", background: "var(--paper-50)", padding: 16, overflowY: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 14 }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-base)", fontWeight: 600, color: "var(--text-strong)" }}>Chats</h2>
          <button
            type="button"
            aria-label="Start a new chat"
            title="Start a new chat"
            onClick={startNewChat}
            disabled={busy}
            style={{ width: 34, height: 34, borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)", background: "var(--surface-card)", color: "var(--text-brand)", display: "inline-flex", alignItems: "center", justifyContent: "center", cursor: busy ? "not-allowed" : "pointer" }}
          >
            <I.Plus size={18} />
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {sessions.length === 0 ? (
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)", padding: "8px 2px" }}>No saved chats yet.</div>
          ) : sessions.map((session) => {
            const active = session.id === activeSessionId;
            return (
              <button
                key={session.id}
                type="button"
                onClick={() => openSession(session.id)}
                disabled={busy}
                style={{ textAlign: "left", borderRadius: "var(--radius-md)", border: active ? "1px solid var(--evergreen-300)" : "1px solid transparent", background: active ? "var(--evergreen-50)" : "transparent", padding: "10px 9px", cursor: busy ? "not-allowed" : "pointer", color: "var(--text-body)" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
                  <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{session.title}</span>
                  <span style={{ flex: "none", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{sessionLabel(session)}</span>
                </div>
                {session.preview ? (
                  <div style={{ marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{session.preview}</div>
                ) : null}
              </button>
            );
          })}
        </div>
      </aside>

      <section style={{ height: "100%", display: "flex", flexDirection: "column", maxWidth: 760, margin: "0 auto", width: "100%", minWidth: 0 }}>
      <header style={{ padding: "24px 28px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--text-strong)" }}>Estate chat</h1>
        <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{subtitle}</p>
      </header>

      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", flexDirection: m.from === "user" ? "row-reverse" : "row" }}>
            {m.from === "ai" ? <Avatar initials="AI" tone="ink" size="sm" /> : <Avatar name="Dana Milligan" size="sm" />}
            <div style={{
              maxWidth: "76%", whiteSpace: m.from === "user" ? "pre-wrap" : "normal", lineHeight: "var(--leading-relaxed)", fontSize: "var(--text-base)",
              padding: "12px 16px", borderRadius: m.from === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              background: m.from === "user" ? "var(--evergreen-700)" : "var(--surface-card)",
              color: m.from === "user" ? "var(--text-inverse)" : "var(--text-body)",
              border: m.from === "user" ? "none" : "1px solid var(--border-subtle)",
              boxShadow: "var(--shadow-xs)",
            }}>
              {m.from === "ai"
                ? (m.text ? <Markdown text={m.text} /> : (busy ? "…" : ""))
                : m.text}
            </div>
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
      </section>
    </div>
  );
}
