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
