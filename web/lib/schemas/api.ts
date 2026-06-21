import { z } from "zod";
import { documentExtractionSchema } from "./documents";
import { alertSchema, estateStateSchema } from "./estate";

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

export const chatRequestSchema = z.object({
  estateId: z.string(),
  message: z.string(),
  topK: z.number().int().positive().optional(),
}).strict();

export const generateLetterRequestSchema = z.object({
  estateId: z.string(),
  letterType: z.string(),
  recipientName: z.string().nullable().optional(),
}).strict();

export const parseDocumentResponseSchema = z.object({
  estateId: z.string(),
  extraction: documentExtractionSchema,
  documentType: z.string(),
  needsTypeSelection: z.boolean(),
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

export const estateResponseSchema = z.object({
  estate: estateStateSchema,
}).strict();

export const seedResponseSchema = z.object({
  estate: estateStateSchema,
  alerts: z.array(alertSchema),
}).strict();
