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
import { meResponseSchema, publicUserSchema } from "./schemas/auth";
import { z } from "zod";
import type {
  Alert,
  ChatRequest,
  EstateState,
  GenerateLetterResponse,
  LoginRequest,
  MeResponse,
  ParseDocumentResponse,
  PublicUser,
  RegisterRequest,
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

export async function getEstate(estateId = DEFAULT_ESTATE_ID): Promise<EstateState> {
  const response = await fetch(`/api/agent/estate/${estateId}`);
  const payload = await response.json();
  return estateResponseSchema.parse(payload).estate;
}

export async function runDeadlineAgent(estateId = DEFAULT_ESTATE_ID): Promise<Alert[]> {
  const request = deadlineAgentRequestSchema.parse({ estateId });
  const response = await fetch("/api/agent/deadline-agent", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
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
