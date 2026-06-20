import { z } from "zod";
import { documentExtractionSchema } from "./documents";
import { alertSchema, estateStateSchema } from "./estate";

export const parseDocumentResponseSchema = z.object({
  estateId: z.string(),
  extraction: documentExtractionSchema,
  alerts: z.array(alertSchema),
});

export const deadlineAgentResponseSchema = z.object({
  estateId: z.string(),
  alerts: z.array(alertSchema),
});

export const generateLetterResponseSchema = z.object({
  estateId: z.string(),
  letterType: z.string(),
  draft: z.string(),
});

export const estateResponseSchema = z.object({
  estate: estateStateSchema,
});

