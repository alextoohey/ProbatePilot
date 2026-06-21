import {
  chatHistoryResponseSchema,
  chatSuggestionsResponseSchema,
  notifyEmailResponseSchema,
  chatRequestSchema,
  completeAlertRequestSchema,
  chatSessionResponseSchema,
  chatSessionsResponseSchema,
  deadlineAgentRequestSchema,
  deadlineAgentResponseSchema,
  estateResponseSchema,
  generateLetterRequestSchema,
  generateLetterResponseSchema,
  parseDocumentResponseSchema,
  saveLetterRequestSchema,
  saveLetterResponseSchema,
  parseDocumentsResponseSchema,
  seedResponseSchema,
} from "./schemas/api";
import { meResponseSchema, publicUserSchema } from "./schemas/auth";
import { z } from "zod";
import type {
  Alert,
  ChatMessage,
  ChatRequest,
  ChatSession,
  EstateState,
  GenerateLetterResponse,
  LoginRequest,
  MeResponse,
  NotifyEmailResponse,
  ParseDocumentResponse,
  ParseDocumentsResponse,
  PublicUser,
  RegisterRequest,
  SavedLetter,
} from "@/types";

const DEFAULT_ESTATE_ID = "demo-milligan";

/** Thrown by auth calls so the UI can show the server's message. */
export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

async function readError(response: Response, fallback: string): Promise<string> {
  const payload = await response.json().catch(() => ({}));
  const detail = (payload as { detail?: unknown; error?: unknown }).detail ?? (payload as { error?: unknown }).error;
  return typeof detail === "string" ? detail : fallback;
}

export async function register(request: RegisterRequest): Promise<{ user: PublicUser; estate: EstateState | null }> {
  const response = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new AuthError(await readError(response, "Could not create your account."), response.status);
  }
  return z
    .object({ user: publicUserSchema, estate: estateResponseSchema.shape.estate.nullable() })
    .parse(await response.json());
}

export async function login(request: LoginRequest): Promise<{ user: PublicUser }> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new AuthError(await readError(response, "Incorrect email or password."), response.status);
  }
  return z.object({ user: publicUserSchema }).parse(await response.json());
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

export async function getMe(): Promise<MeResponse | null> {
  const response = await fetch("/api/auth/me", { cache: "no-store" });
  if (response.status === 401) return null;
  if (!response.ok) throw new AuthError(await readError(response, "Could not load your account."), response.status);
  return meResponseSchema.parse(await response.json());
}

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

export async function completeAlert(estateId = DEFAULT_ESTATE_ID, alertId: string): Promise<EstateState> {
  const request = completeAlertRequestSchema.parse({ estateId, alertId });
  const response = await fetch("/api/agent/complete-alert", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "We couldn't mark that step complete."));
  }
  const payload = await response.json();
  return estateResponseSchema.parse(payload).estate;
}

export async function parseDocument(
  file: File,
  estateId = DEFAULT_ESTATE_ID,
  documentType?: string,
): Promise<ParseDocumentResponse> {
  const body = new FormData();
  body.append("estateId", estateId);
  if (documentType) body.append("documentType", documentType);
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

export async function parseDocuments(
  files: File[],
  estateId = DEFAULT_ESTATE_ID,
): Promise<ParseDocumentsResponse> {
  const body = new FormData();
  body.append("estateId", estateId);
  for (const file of files) body.append("files", file);
  const response = await fetch("/api/agent/parse-documents", { method: "POST", body });
  if (!response.ok) {
    let message = "We couldn't parse those documents. Please reupload clearer files.";
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") message = payload.detail;
    } catch {
      // Keep the friendly default when the proxy returns a non-JSON error body.
    }
    throw new Error(message);
  }
  const payload = await response.json();
  return parseDocumentsResponseSchema.parse(payload);
}

export async function deleteDocument(estateId: string, documentId: string): Promise<void> {
  const response = await fetch(`/api/agent/document/${encodeURIComponent(estateId)}/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Could not delete that document."));
  }
}

export async function getChatHistory(estateId = DEFAULT_ESTATE_ID, sessionId?: string | null, signal?: AbortSignal): Promise<ChatMessage[]> {
  const query = sessionId ? `?sessionId=${encodeURIComponent(sessionId)}` : "";
  const response = await fetch(`/api/agent/chat-history/${encodeURIComponent(estateId)}${query}`, { signal });
  if (!response.ok) return [];
  const payload = await response.json();
  return chatHistoryResponseSchema.parse(payload).messages;
}

export async function getChatSuggestions(estateId = DEFAULT_ESTATE_ID, signal?: AbortSignal): Promise<string[]> {
  const response = await fetch("/api/agent/chat-suggestions", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ estateId }),
    signal,
  });
  if (!response.ok) return [];
  const payload = await response.json();
  return chatSuggestionsResponseSchema.parse(payload).suggestions;
}

export async function getChatSessions(estateId = DEFAULT_ESTATE_ID, signal?: AbortSignal): Promise<ChatSession[]> {
  const response = await fetch(`/api/agent/chat-sessions/${encodeURIComponent(estateId)}`, { signal });
  if (!response.ok) return [];
  const payload = await response.json();
  return chatSessionsResponseSchema.parse(payload).sessions;
}

export async function createChatSession(estateId = DEFAULT_ESTATE_ID): Promise<{ session: ChatSession; messages: ChatMessage[] }> {
  const response = await fetch(`/api/agent/chat-sessions/${encodeURIComponent(estateId)}`, { method: "POST" });
  const payload = await response.json();
  const parsed = chatSessionResponseSchema.parse(payload);
  return { session: parsed.session, messages: parsed.messages };
}

export async function sendAlertEmail(
  estateId = DEFAULT_ESTATE_ID,
  recipientEmail?: string | null,
  kind: "alerts" | "weekly" = "alerts",
): Promise<NotifyEmailResponse> {
  const response = await fetch("/api/agent/notify/email", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ estateId, recipientEmail, kind }),
  });
  const payload = await response.json();
  return notifyEmailResponseSchema.parse(payload);
}

export async function openChatStream(request: ChatRequest): Promise<ReadableStream<Uint8Array> | null> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(chatRequestSchema.parse(request)),
  });
  return response.body;
}

export async function saveLetter(
  estateId: string,
  letterType: string,
  draft: string,
  recipientName?: string | null,
): Promise<SavedLetter> {
  const request = saveLetterRequestSchema.parse({ estateId, letterType, draft, recipientName });
  const response = await fetch("/api/agent/save-letter", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  const payload = await response.json();
  return saveLetterResponseSchema.parse(payload).letter;
}

export async function generateLetter(
  letterType: string,
  estateId = DEFAULT_ESTATE_ID,
  recipientName?: string | null,
  instructions?: string | null,
): Promise<GenerateLetterResponse> {
  const request = generateLetterRequestSchema.parse({ estateId, letterType, recipientName, instructions });
  const response = await fetch("/api/agent/generate-letter", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  const payload = await response.json();
  return generateLetterResponseSchema.parse(payload);
}
