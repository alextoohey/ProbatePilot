"use client";

import { useState } from "react";
import { generateLetter } from "@/lib/agentClient";

export function LetterPreview() {
  const [draft, setDraft] = useState("");

  return (
    <section className="space-y-3">
      <button
        className="rounded-md border bg-white px-4 py-2"
        onClick={async () => setDraft((await generateLetter("creditor_notice")).draft)}
      >
        Generate creditor notice
      </button>
      {draft ? <pre className="whitespace-pre-wrap rounded-md border bg-white p-4 text-sm">{draft}</pre> : null}
    </section>
  );
}
