import type { AnyDocumentExtraction } from "./documents";
import type { Alert, EstateState } from "./estate";

export interface SearchResult {
  text: string;
  score: number;
  source?: string | null;
  documentType?: string | null;
  chunkIndex?: number | null;
  estateId: string;
}

export interface ParseDocumentResponse {
  estateId: string;
  fileName?: string | null;
  extraction: AnyDocumentExtraction;
  documentType: string;
  needsTypeSelection: boolean;
  reviewMessage?: string | null;
  alerts: Alert[];
}

export interface ParseDocumentFailure {
  fileName: string;
  detail: string;
  statusCode: number;
}

export interface ParseDocumentsResponse {
  estateId: string;
  results: ParseDocumentResponse[];
  failed: ParseDocumentFailure[];
  alerts: Alert[];
}

export interface DeadlineAgentRequest {
  estateId: string;
}

export interface DeadlineAgentResponse {
  estateId: string;
  alerts: Alert[];
}

export interface CompleteAlertRequest {
  estateId: string;
  alertId: string;
}

export interface ChatRequest {
  estateId: string;
  message: string;
  topK?: number;
  sessionId?: string | null;
}

export interface ChatMessage {
  role: string;
  content: string;
  createdAt: string;
}

export interface ChatHistoryResponse {
  estateId: string;
  sessionId?: string | null;
  messages: ChatMessage[];
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  preview?: string | null;
}

export interface ChatSessionsResponse {
  estateId: string;
  sessions: ChatSession[];
}

export interface ChatSessionResponse {
  estateId: string;
  session: ChatSession;
  messages: ChatMessage[];
}

export interface ChatSuggestionsResponse {
  estateId: string;
  suggestions: string[];
}

export interface NotifyEmailResponse {
  estateId: string;
  sent: boolean;
  reason: string;
  recipient?: string | null;
  alertCount: number;
  subject: string;
  body: string;
}

export interface GenerateLetterRequest {
  estateId: string;
  letterType: string;
  recipientName?: string | null;
  instructions?: string | null;
}

export interface GenerateLetterResponse {
  estateId: string;
  letterType: string;
  draft: string;
}

export interface EstateResponse {
  estate: EstateState;
}
