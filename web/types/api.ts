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
  extraction: AnyDocumentExtraction;
  documentType: string;
  needsTypeSelection: boolean;
  alerts: Alert[];
}

export interface DeadlineAgentRequest {
  estateId: string;
}

export interface DeadlineAgentResponse {
  estateId: string;
  alerts: Alert[];
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

export interface GenerateLetterRequest {
  estateId: string;
  letterType: string;
  recipientName?: string | null;
}

export interface GenerateLetterResponse {
  estateId: string;
  letterType: string;
  draft: string;
}

export interface EstateResponse {
  estate: EstateState;
}
