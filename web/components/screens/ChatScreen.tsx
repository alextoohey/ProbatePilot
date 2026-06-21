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

// Initialisms the TTS otherwise tries to pronounce as a word (e.g. "EIN" → "ine").
// Map them to space-separated letters so Deepgram reads them letter-by-letter.
// Keys must be the exact upper-case token; only whole-word matches are replaced.
const SPELL_OUT: Record<string, string> = {
  EIN: "E I N",
  IRS: "I R S",
  SSN: "S S N",
  LLC: "L L C",
  TOD: "T O D",
  POD: "P O D",
  FBO: "F B O",
  UTMA: "U T M A",
  HOA: "H O A",
  APN: "A P N",
};

function spellOutInitialisms(text: string): string {
  return text
    // form codes like DE-140 or GC-050 → spell the letters, keep the number
    // ("DE-140" → "D E 140"). The number is read normally by the TTS.
    .replace(/\b([A-Z]{1,4})-(\d{1,5})\b/g, (_m, letters: string, num: string) => `${letters.split("").join(" ")} ${num}`)
    // known initialisms that would otherwise be read as a word ("EIN" → "ine")
    .replace(/\b[A-Z]{2,5}\b/g, (m) => SPELL_OUT[m] ?? m);
}

// Markdown leans on line breaks (list items, soft paragraph breaks) instead of
// terminal punctuation. TTS ignores bare newlines, so it runs separate points
// together as one breathless sentence. Give every line that doesn't already end
// in punctuation a period so the voice actually pauses between thoughts.
function ensureSentencePauses(text: string): string {
  return text
    .split("\n")
    .map((line) => {
      const t = line.trim();
      if (!t) return "";
      return /[.!?:;,]$/.test(t) ? t : `${t}.`;
    })
    .join("\n");
}

// Turn markdown/rich text into something natural to *hear*. The agent replies in
// markdown for the screen, but TTS reads syntax literally ("star star", "dash
// dash"), so strip formatting before sending text to Deepgram.
function stripForSpeech(md: string): string {
  const stripped = md
    // fenced + inline code → keep the words, drop the backticks
    .replace(/```[\s\S]*?```/g, (b) => b.replace(/```/g, " "))
    .replace(/`([^`]+)`/g, "$1")
    // images / links → keep the visible text only
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    // headings, blockquotes, list bullets at line starts
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s{0,3}>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    // horizontal rules: ---, ***, ___ on their own line
    .replace(/^\s*([-*_])(?:\s*\1){2,}\s*$/gm, "")
    // bold / italic / strikethrough emphasis markers
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/~~(.*?)~~/g, "$1")
    // tidy: drop leftover symbols, turn dashes-as-asides into spoken pauses
    .replace(/[*_`#>]/g, "")
    .replace(/\s+[—–]\s+/g, ", ")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n");
  return spellOutInitialisms(ensureSentencePauses(stripped)).trim();
}

// Document types that carry no useful name — skip them in the greeting rather
// than telling the executor we read an "unknown".
const UNKNOWN_DOC_TYPES = new Set(["unknown", "unknown_document", "other", ""]);

// Build the opening message from the real estate: who the executor is, who died,
// and which named documents have actually been parsed.
function buildGreeting(deceasedName: string, executorName?: string | null, documentTypes: string[] = []): string {
  const hello = executorName ? `Hi ${firstName(executorName)}, ` : "Hi there, ";
  const tail = `Ask me anything about ${firstName(deceasedName)}'s estate, or I can tell you the most urgent thing to handle.`;
  const known = Array.from(
    new Set(
      documentTypes
        .map((t) => (t || "").trim().toLowerCase())
        .filter((t) => !UNKNOWN_DOC_TYPES.has(t)),
    ),
  ).map((t) => t.replace(/_/g, " "));
  if (known.length === 0) return `${hello}${tail}`;
  return `${hello}I've read the ${humanList(known)}. ${tail}`;
}

export function ChatScreen({ estate }: Props) {
  const [suggestions, setSuggestions] = React.useState<string[]>(DEFAULT_SUGGESTIONS);
  const [msgs, setMsgs] = React.useState<Msg[]>(() => [{ from: "ai", text: buildGreeting(estate.deceasedName) }]);
  const [sessions, setSessions] = React.useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  const [loadingChats, setLoadingChats] = React.useState(true);
  const [subtitle, setSubtitle] = React.useState(`Grounded in ${firstName(estate.deceasedName)}'s documents, not legal advice`);
  const [draft, setDraft] = React.useState("");
  const [recording, setRecording] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  // Hands-free voice-to-voice conversation mode (Deepgram STT + TTS in a loop).
  const [voiceMode, setVoiceMode] = React.useState(false);
  const [voiceStatus, setVoiceStatus] = React.useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  // Covers the brief flash of the placeholder greeting before the real estate
  // and saved history load.
  const [loading, setLoading] = React.useState(true);
  const endRef = React.useRef<HTMLDivElement>(null);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);
  const voiceModeRef = React.useRef(false);
  const voiceStreamRef = React.useRef<MediaStream | null>(null);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  // Load the real estate (for the greeting + suggestions) and any prior chat
  // history. If there's saved history, restore the conversation; otherwise show
  // a greeting built from this estate's executor, deceased, and parsed documents.
  React.useEffect(() => {
    if (!estate.id) { setLoading(false); setLoadingChats(false); return; }
    let cancelled = false;
    setLoadingChats(true);
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
      setLoadingChats(false);
    }).finally(() => {
      if (!cancelled) {
        setLoading(false);
        setLoadingChats(false);
      }
    });
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

  async function send(text?: string, viaVoice = false): Promise<string> {
    const t = (text ?? draft).trim();
    if (!t || busy) return "";
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
      return full;
    } catch {
      setMsgs((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { from: "ai", text: "I couldn't reach the estate service. Make sure the agent is running on :8000, then try again." };
        return copy;
      });
      return "";
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

  async function transcribeBlob(blob: Blob): Promise<string> {
    try {
      const res = await fetch("/api/voice/transcribe", { method: "POST", headers: { "content-type": blob.type || "audio/webm" }, body: blob });
      if (!res.ok) throw new Error(`transcribe ${res.status}`);
      const { transcript } = await res.json();
      return (transcript as string) ?? "";
    } catch (err) {
      console.error(err);
      return "";
    }
  }

  // Hold-to-speak: one push-to-talk turn that also reads the reply back aloud.
  async function transcribe(blob: Blob) {
    const transcript = await transcribeBlob(blob);
    if (!transcript) return;
    const reply = await send(transcript);
    if (reply.trim()) void speak(reply);
  }

  // Speak text via Deepgram TTS. Resolves when playback ends so the voice loop
  // can wait before listening again (and so it never records its own voice).
  function speak(text: string): Promise<void> {
    return new Promise<void>((resolve) => {
      (async () => {
        try {
          const spoken = stripForSpeech(text);
          if (!spoken) return resolve();
          const res = await fetch("/api/voice/speak", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: spoken }) });
          if (!res.ok) return resolve();
          const buf = await res.arrayBuffer();
          const url = URL.createObjectURL(new Blob([buf], { type: "audio/mpeg" }));
          const audio = new Audio(url);
          audioRef.current = audio;
          const done = () => {
            URL.revokeObjectURL(url);
            if (audioRef.current === audio) audioRef.current = null;
            resolve();
          };
          audio.onended = done;
          audio.onerror = () => done();
          await audio.play().catch(done);
        } catch (err) {
          console.error(err);
          resolve();
        }
      })();
    });
  }

  // ── Voice-to-voice (hands-free) ──────────────────────────────────────────
  // Record one spoken turn, auto-stopping after a short silence so the user
  // doesn't need to hold anything. Returns the captured audio (or null).
  function recordVoiceTurn(stream: MediaStream): Promise<Blob | null> {
    return new Promise<Blob | null>((resolve) => {
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      const chunks: Blob[] = [];
      let settled = false;

      const ac = new AudioContext();
      const source = ac.createMediaStreamSource(stream);
      const analyser = ac.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);

      const STEP = 100; // ms between volume checks
      const SILENCE_MS = 1100; // trailing silence that ends a turn
      const NO_SPEECH_MS = 8000; // give up if nothing is said
      const MAX_MS = 20000; // hard cap on a single turn
      const THRESHOLD = 0.015; // RMS speech/silence cutoff
      let speechStarted = false;
      let silenceFor = 0;
      let elapsed = 0;

      const finish = (blob: Blob | null) => {
        if (settled) return;
        settled = true;
        clearInterval(timer);
        ac.close().catch(() => {});
        resolve(blob);
      };
      const stop = () => { if (recorder.state !== "inactive") recorder.stop(); };

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = () => finish(chunks.length ? new Blob(chunks, { type: recorder.mimeType }) : null);

      const timer = setInterval(() => {
        if (!voiceModeRef.current) { stop(); return; }
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) { const v = (data[i] - 128) / 128; sum += v * v; }
        const rms = Math.sqrt(sum / data.length);
        elapsed += STEP;
        if (rms > THRESHOLD) { speechStarted = true; silenceFor = 0; }
        else if (speechStarted) { silenceFor += STEP; }
        if (speechStarted && silenceFor >= SILENCE_MS) stop();
        else if (!speechStarted && elapsed >= NO_SPEECH_MS) stop();
        else if (elapsed >= MAX_MS) stop();
      }, STEP);

      recorder.start();
    });
  }

  // The conversation loop: listen → transcribe → answer → speak → repeat,
  // until the user turns voice mode off (or the component unmounts).
  async function runVoiceLoop(stream: MediaStream) {
    while (voiceModeRef.current) {
      setVoiceStatus("listening");
      let blob: Blob | null = null;
      try {
        blob = await recordVoiceTurn(stream);
      } catch (err) {
        console.error(err);
        break;
      }
      if (!voiceModeRef.current) break;
      if (!blob) continue; // nothing captured — keep listening

      setVoiceStatus("thinking");
      const transcript = await transcribeBlob(blob);
      if (!voiceModeRef.current) break;
      if (!transcript.trim()) continue;

      const reply = await send(transcript);
      if (!voiceModeRef.current) break;
      if (reply.trim()) {
        setVoiceStatus("speaking");
        await speak(reply);
      }
    }
    setVoiceStatus("idle");
  }

  async function startVoiceMode() {
    if (voiceModeRef.current) return;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.error(err);
      return;
    }
    voiceStreamRef.current = stream;
    voiceModeRef.current = true;
    setVoiceMode(true);
    void runVoiceLoop(stream);
  }

  function stopVoiceMode() {
    voiceModeRef.current = false;
    setVoiceMode(false);
    setVoiceStatus("idle");
    if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    if (voiceStreamRef.current) {
      voiceStreamRef.current.getTracks().forEach((t) => t.stop());
      voiceStreamRef.current = null;
    }
  }

  function toggleVoiceMode() {
    if (voiceModeRef.current) stopVoiceMode();
    else void startVoiceMode();
  }

  // Tear everything down if the chat unmounts mid-conversation.
  React.useEffect(() => () => {
    voiceModeRef.current = false;
    if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    if (audioRef.current) audioRef.current.pause();
    voiceStreamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

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
            disabled={busy || loadingChats}
            style={{ width: 34, height: 34, borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)", background: "var(--surface-card)", color: "var(--text-brand)", display: "inline-flex", alignItems: "center", justifyContent: "center", cursor: busy || loadingChats ? "not-allowed" : "pointer" }}
          >
            <I.Plus size={18} />
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {loadingChats ? (
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)", padding: "8px 2px" }}>Loading saved chats...</div>
          ) : sessions.length === 0 ? (
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)", padding: "8px 2px" }}>No saved chats yet.</div>
          ) : sessions.map((session) => {
            const active = session.id === activeSessionId;
            return (
              <button
                key={session.id}
                type="button"
                onClick={() => openSession(session.id)}
                disabled={busy || loadingChats}
                style={{ textAlign: "left", borderRadius: "var(--radius-md)", border: active ? "1px solid var(--evergreen-300)" : "1px solid transparent", background: active ? "var(--evergreen-50)" : "transparent", padding: "10px 9px", cursor: busy || loadingChats ? "not-allowed" : "pointer", color: "var(--text-body)" }}
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
        {voiceMode ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: "var(--text-sm)", color: "var(--text-brand)", fontWeight: 600 }}>
            <span aria-hidden style={{ width: 9, height: 9, borderRadius: "999px", background: "var(--evergreen-600)",
              animation: voiceStatus === "speaking" || voiceStatus === "listening" ? "executorPulse 1.1s ease-in-out infinite" : "none" }} />
            {voiceStatus === "listening" ? "Listening…" : voiceStatus === "thinking" ? "Thinking…" : voiceStatus === "speaking" ? "Speaking…" : "Voice conversation on"}
            <style>{`@keyframes executorPulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: .35; transform: scale(.7); } }`}</style>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
            {suggestions.map((s) => (
              <button key={s} onClick={() => send(s)} style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", color: "var(--text-brand)", background: "var(--evergreen-50)", border: "1px solid var(--evergreen-200)", borderRadius: "var(--radius-full)", padding: "6px 12px", cursor: "pointer" }}>{s}</button>
            ))}
          </div>
        )}
        <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
          <button
            onClick={toggleVoiceMode}
            aria-label={voiceMode ? "Turn off voice conversation" : "Start voice conversation"}
            aria-pressed={voiceMode}
            title={voiceMode ? "Turn off voice conversation" : "Talk hands-free — I'll speak back"}
            style={{ width: 44, height: 44, flex: "none", borderRadius: "var(--radius-md)", cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center",
              background: voiceMode ? "var(--evergreen-700)" : "var(--surface-card)", color: voiceMode ? "var(--text-inverse)" : "var(--text-muted)",
              border: voiceMode ? "1px solid var(--evergreen-700)" : "1px solid var(--border-default)", transition: "all var(--transition-fast)" }}>
            <I.Headset size={20} />
          </button>
          <button
            disabled={voiceMode}
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onMouseLeave={() => recording && stopRecording()}
            onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
            onTouchEnd={(e) => { e.preventDefault(); stopRecording(); }}
            aria-label="Hold to speak"
            style={{ width: 44, height: 44, flex: "none", borderRadius: "var(--radius-md)", cursor: voiceMode ? "not-allowed" : "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center",
              opacity: voiceMode ? 0.4 : 1,
              background: recording ? "var(--evergreen-700)" : "var(--surface-card)", color: recording ? "var(--text-inverse)" : "var(--text-muted)",
              border: recording ? "1px solid var(--evergreen-700)" : "1px solid var(--border-default)", transition: "all var(--transition-fast)" }}>
            <I.Mic size={20} />
          </button>
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={1}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder={voiceMode ? "Voice conversation on — just speak" : recording ? "Listening…" : "Ask about this estate"}
            style={{ flex: 1, resize: "none", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)", lineHeight: 1.5, color: "var(--text-body)",
              background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "11px 14px", outline: "none", minHeight: 44, boxSizing: "border-box" }} />
          <Button variant="primary" onClick={() => send()} disabled={busy} leadingIcon={<I.Send size={16} />} style={{ height: 44 }}>Send</Button>
        </div>
      </div>
      </section>
    </div>
  );
}
