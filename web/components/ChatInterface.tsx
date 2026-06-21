"use client";

import { useRef, useState } from "react";
import { openChatStream } from "@/lib/agentClient";
import { VoiceButton } from "@/components/VoiceButton";

export function ChatInterface() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [voiceMode, setVoiceMode] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  async function sendMessage() {
    setAnswer("");
    const stream = await openChatStream({ estateId: "demo-milligan", message });
    const reader = stream?.getReader();
    const decoder = new TextDecoder();
    if (!reader) return;

    let full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ") || line.includes("[DONE]")) continue;
        const parsed = JSON.parse(line.replace("data: ", ""));
        full += parsed.token;
        setAnswer((current) => current + parsed.token);
      }
    }

    if (voiceMode && full.trim()) {
      await speak(full);
    }
  }

  async function speak(text: string) {
    setSpeaking(true);
    try {
      const response = await fetch("/api/voice/speak", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) throw new Error(`Speak failed: ${response.status}`);
      const buffer = await response.arrayBuffer();
      const url = URL.createObjectURL(new Blob([buffer], { type: "audio/mpeg" }));
      const audio = audioRef.current ?? new Audio();
      audioRef.current = audio;
      audio.src = url;
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (err) {
      console.error(err);
    } finally {
      setSpeaking(false);
    }
  }

  return (
    <div className="space-y-4">
      <textarea
        className="min-h-32 w-full rounded-md border p-3"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Ask about this estate"
      />
      <div className="flex flex-wrap items-center gap-3">
        <button className="rounded-md bg-slate-900 px-4 py-2 text-white" onClick={sendMessage}>
          Send
        </button>
        <VoiceButton onTranscript={(text) => setMessage((current) => (current ? `${current} ${text}` : text))} />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={voiceMode}
            onChange={(event) => setVoiceMode(event.target.checked)}
          />
          Voice mode {speaking ? "(speaking…)" : ""}
        </label>
      </div>
      {answer ? <div className="rounded-md border bg-white p-4 leading-7">{answer}</div> : null}
    </div>
  );
}
