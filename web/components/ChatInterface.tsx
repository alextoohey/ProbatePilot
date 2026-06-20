"use client";

import { useState } from "react";
import { openChatStream } from "@/lib/agentClient";

export function ChatInterface() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");

  async function sendMessage() {
    setAnswer("");
    const stream = await openChatStream({ estateId: "demo-milligan", message });
    const reader = stream?.getReader();
    const decoder = new TextDecoder();
    if (!reader) return;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ") || line.includes("[DONE]")) continue;
        const parsed = JSON.parse(line.replace("data: ", ""));
        setAnswer((current) => current + parsed.token);
      }
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
      <button className="rounded-md bg-slate-900 px-4 py-2 text-white" onClick={sendMessage}>
        Send
      </button>
      {answer ? <div className="rounded-md border bg-white p-4 leading-7">{answer}</div> : null}
    </div>
  );
}
