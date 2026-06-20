"use client";

import { useState } from "react";
import { parseDocument } from "@/lib/agentClient";

export function DocumentUpload() {
  const [status, setStatus] = useState("No document uploaded");

  async function upload(file: File) {
    setStatus("Parsing document...");
    try {
      await parseDocument(file);
      setStatus("Document parsed");
    } catch {
      setStatus("Upload failed");
    }
  }

  return (
    <label className="block rounded-md border border-dashed bg-white p-8 text-center">
      <input
        className="sr-only"
        type="file"
        accept=".pdf,.txt,.png,.jpg,.jpeg"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
        }}
      />
      <span className="font-medium">Upload estate document</span>
      <span className="mt-2 block text-sm text-slate-600">{status}</span>
    </label>
  );
}
