import {
  chatRequestSchema,
  deadlineAgentRequestSchema,
  deadlineAgentResponseSchema,
  estateResponseSchema,
  generateLetterRequestSchema,
  generateLetterResponseSchema,
  parseDocumentResponseSchema,
  seedResponseSchema,
} from "./schemas/api";
import type {
  Alert,
  ChatRequest,
  EstateState,
  GenerateLetterResponse,
  ParseDocumentResponse,
} from "@/types";

const DEFAULT_ESTATE_ID = "demo-milligan";

export async function seedEstate(): Promise<{ estate: EstateState; alerts: Alert[] }> {
  const response = await fetch("/api/agent/seed", { method: "POST" });
  const payload = await response.json();
  return seedResponseSchema.parse(payload);
}

export async function getEstate(estateId = DEFAULT_ESTATE_ID, signal?: AbortSignal): Promise<EstateState> {
  const response = await fetch(`/api/agent/estate/${estateId}`, { signal });
  const payload = await response.json();
  return estateResponseSchema.parse(payload).estate;
}

export async function runDeadlineAgent(estateId = DEFAULT_ESTATE_ID, signal?: AbortSignal): Promise<Alert[]> {
  const request = deadlineAgentRequestSchema.parse({ estateId });
  const response = await fetch("/api/agent/deadline-agent", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  const payload = await response.json();
  return deadlineAgentResponseSchema.parse(payload).alerts;
}

export async function parseDocument(file: File, estateId = DEFAULT_ESTATE_ID): Promise<ParseDocumentResponse> {
  const body = new FormData();
  body.append("estateId", estateId);
  body.append("file", file);
  const response = await fetch("/api/agent/parse-document", { method: "POST", body });
  if (!response.ok) {
    let message = "We couldn't parse that document. Please reupload a clearer file.";
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") message = payload.detail;
    } catch {
      // Keep the friendly default when the proxy returns a non-JSON error body.
    }
    throw new Error(message);
  }
  const payload = await response.json();
  return parseDocumentResponseSchema.parse(payload);
}

export async function openChatStream(request: ChatRequest): Promise<ReadableStream<Uint8Array> | null> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(chatRequestSchema.parse(request)),
  });
  return response.body;
}

export async function generateLetter(
  letterType: string,
  estateId = DEFAULT_ESTATE_ID,
): Promise<GenerateLetterResponse> {
  const request = generateLetterRequestSchema.parse({ estateId, letterType });
  const response = await fetch("/api/agent/generate-letter", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  const payload = await response.json();
  return generateLetterResponseSchema.parse(payload);
}
