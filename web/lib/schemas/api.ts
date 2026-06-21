import { z } from "zod";
import { documentExtractionSchema } from "./documents";
import { alertSchema, estateStateSchema, savedLetterSchema } from "./estate";

export const searchResultSchema = z.object({
  text: z.string(),
  score: z.number(),
  source: z.string().nullable().optional(),
  documentType: z.string().nullable().optional(),
  chunkIndex: z.number().int().nullable().optional(),
  estateId: z.string(),
}).strict();

export const deadlineAgentRequestSchema = z.object({
  estateId: z.string(),
}).strict();

export const completeAlertRequestSchema = z.object({
  estateId: z.string(),
  alertId: z.string(),
}).strict();

export const chatRequestSchema = z.object({
  estateId: z.string(),
  message: z.string(),
  topK: z.number().int().positive().optional(),
  sessionId: z.string().nullable().optional(),
}).strict();

export const generateLetterRequestSchema = z.object({
  estateId: z.string(),
  letterType: z.string(),
  recipientName: z.string().nullable().optional(),
  instructions: z.string().nullable().optional(),
}).strict();

export const parseDocumentResponseSchema = z.object({
  estateId: z.string(),
  fileName: z.string().nullable().optional(),
  extraction: documentExtractionSchema,
  documentType: z.string(),
  needsTypeSelection: z.boolean(),
  reviewMessage: z.string().nullable().optional(),
  alerts: z.array(alertSchema),
}).strict();

export const parseDocumentFailureSchema = z.object({
  fileName: z.string(),
  detail: z.string(),
  statusCode: z.number().int(),
}).strict();

export const parseDocumentsResponseSchema = z.object({
  estateId: z.string(),
  results: z.array(parseDocumentResponseSchema),
  failed: z.array(parseDocumentFailureSchema),
  alerts: z.array(alertSchema),
}).strict();

export const deadlineAgentResponseSchema = z.object({
  estateId: z.string(),
  alerts: z.array(alertSchema),
}).strict();

export const generateLetterResponseSchema = z.object({
  estateId: z.string(),
  letterType: z.string(),
  draft: z.string(),
}).strict();

export const chatMessageSchema = z.object({
  role: z.string(),
  content: z.string(),
  createdAt: z.string(),
}).strict();

export const chatHistoryResponseSchema = z.object({
  estateId: z.string(),
  sessionId: z.string().nullable().optional(),
  messages: z.array(chatMessageSchema),
}).strict();

export const saveLetterRequestSchema = z.object({
  estateId: z.string(),
  letterType: z.string(),
  recipientName: z.string().nullable().optional(),
  draft: z.string(),
}).strict();

export const saveLetterResponseSchema = z.object({
  estateId: z.string(),
  letter: savedLetterSchema,
}).strict();

export const chatSessionSchema = z.object({
  id: z.string(),
  title: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
  messageCount: z.number().int(),
  preview: z.string().nullable().optional(),
}).strict();

export const chatSessionsResponseSchema = z.object({
  estateId: z.string(),
  sessions: z.array(chatSessionSchema),
}).strict();

export const chatSessionResponseSchema = z.object({
  estateId: z.string(),
  session: chatSessionSchema,
  messages: z.array(chatMessageSchema),
}).strict();

export const chatSuggestionsResponseSchema = z.object({
  estateId: z.string(),
  suggestions: z.array(z.string()),
}).strict();

export const estateResponseSchema = z.object({
  estate: estateStateSchema,
}).strict();

export const seedResponseSchema = z.object({
  estate: estateStateSchema,
  alerts: z.array(alertSchema),
}).strict();
