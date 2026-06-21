import { z } from "zod";
import { assetSchema, beneficiarySchema } from "./estate";

const baseDocumentExtractionSchema = z.object({
  confidence: z.number().min(0).max(1),
  rawChunks: z.array(z.string()),
}).strict();

export const willExtractionSchema = baseDocumentExtractionSchema.extend({
  documentType: z.literal("will"),
  executorName: z.string().nullable().optional(),
  beneficiaries: z.array(beneficiarySchema),
  assets: z.array(assetSchema),
  trustClauses: z.array(z.string()),
  specialInstructions: z.array(z.string()),
  codicils: z.array(z.string()),
}).strict();

export const bankStatementExtractionSchema = baseDocumentExtractionSchema.extend({
  documentType: z.literal("bank_statement"),
  institution: z.string().nullable().optional(),
  accountLast4: z.string().nullable().optional(),
  accountType: z.string().nullable().optional(),
  balance: z.number().nullable().optional(),
  statementDate: z.string().nullable().optional(),
  notableTransactions: z.array(z.string()),
}).strict();

export const deedExtractionSchema = baseDocumentExtractionSchema.extend({
  documentType: z.literal("deed"),
  propertyAddress: z.string().nullable().optional(),
  apn: z.string().nullable().optional(),
  legalDescription: z.string().nullable().optional(),
  grantor: z.string().nullable().optional(),
  grantee: z.string().nullable().optional(),
  recordedDate: z.string().nullable().optional(),
  estimatedValue: z.number().nullable().optional(),
}).strict();

export const unknownDocumentExtractionSchema = baseDocumentExtractionSchema.extend({
  documentType: z.literal("unknown"),
  reason: z.string(),
}).strict();

export const documentExtractionSchema = z.discriminatedUnion("documentType", [
  willExtractionSchema,
  bankStatementExtractionSchema,
  deedExtractionSchema,
  unknownDocumentExtractionSchema,
]);
