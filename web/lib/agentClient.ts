import {
  deadlineAgentResponseSchema,
  estateResponseSchema,
  generateLetterResponseSchema,
  parseDocumentResponseSchema,
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
  return {
    estate: estateResponseSchema.parse({ estate: payload.estate }).estate,
    alerts: payload.alerts,
  };
}

export async function getEstate(estateId = DEFAULT_ESTATE_ID): Promise<EstateState> {
  const response = await fetch(`/api/agent/estate/${estateId}`);
  const payload = await response.json();
  return estateResponseSchema.parse(payload).estate;
}

export async function runDeadlineAgent(estateId = DEFAULT_ESTATE_ID): Promise<Alert[]> {
  const response = await fetch("/api/agent/deadline-agent", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ estateId }),
  });
  const payload = await response.json();
  return deadlineAgentResponseSchema.parse(payload).alerts;
}

export async function parseDocument(file: File, estateId = DEFAULT_ESTATE_ID): Promise<ParseDocumentResponse> {
  const body = new FormData();
  body.append("estateId", estateId);
  body.append("file", file);
  const response = await fetch("/api/agent/parse-document", { method: "POST", body });
  const payload = await response.json();
  return parseDocumentResponseSchema.parse(payload);
}

export async function openChatStream(request: ChatRequest): Promise<ReadableStream<Uint8Array> | null> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  return response.body;
}

export async function generateLetter(
  letterType: string,
  estateId = DEFAULT_ESTATE_ID,
): Promise<GenerateLetterResponse> {
  const response = await fetch("/api/agent/generate-letter", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ estateId, letterType }),
  });
  const payload = await response.json();
  return generateLetterResponseSchema.parse(payload);
}
