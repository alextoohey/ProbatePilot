import { z } from "zod";

export const estatePhaseSchema = z.union([
  z.literal(1),
  z.literal(2),
  z.literal(3),
  z.literal(4),
  z.literal(5),
  z.literal(6),
]);

export const executorSchema = z.object({
  name: z.string(),
  email: z.string(),
}).strict();

export const assetSchema = z.object({
  id: z.string(),
  type: z.enum(["real_estate", "bank_account", "retirement", "vehicle", "personal_property", "other"]),
  description: z.string(),
  estimatedValue: z.number().nullable().optional(),
  appraised: z.boolean(),
  appraisedValue: z.number().nullable().optional(),
  beneficiaryNamed: z.boolean().nullable().optional(),
}).strict();

export const debtSchema = z.object({
  id: z.string(),
  creditor: z.string(),
  amount: z.number(),
  type: z.enum(["secured", "unsecured", "priority"]),
  notified: z.boolean(),
  notifiedDate: z.string().nullable().optional(),
  claimFiled: z.boolean().nullable().optional(),
}).strict();

export const beneficiarySchema = z.object({
  id: z.string(),
  name: z.string(),
  share: z.string().nullable().optional(),
  specificBequest: z.string().nullable().optional(),
  contactInfo: z.string().nullable().optional(),
}).strict();

export const uploadedDocumentSchema = z.object({
  id: z.string(),
  fileName: z.string(),
  documentType: z.string(),
  uploadedAt: z.string(),
  source: z.string().nullable().optional(),
}).strict();

export const taskSchema = z.object({
  id: z.string(),
  title: z.string(),
  status: z.enum(["todo", "in_progress", "done", "blocked"]),
  phase: estatePhaseSchema,
  dueDate: z.string().nullable().optional(),
  relatedAlertId: z.string().nullable().optional(),
}).strict();

export const alertSchema = z.object({
  id: z.string(),
  severity: z.enum(["critical", "warning", "info"]),
  type: z.enum(["deadline", "liability", "missing_doc", "rule_violation"]),
  title: z.string(),
  body: z.string(),
  rule: z.string(),
  daysRemaining: z.number().nullable().optional(),
  timingStatus: z.enum(["dated", "blocking", "prerequisite", "missing_data", "no_deadline"]).optional(),
  actionRequired: z.string(),
  whatYouNeed: z.array(z.string()),
  steps: z.array(z.string()),
  createdAt: z.string(),
  dismissed: z.boolean(),
}).strict();

export const estateStateSchema = z.object({
  id: z.string(),
  deceasedName: z.string(),
  dateOfDeath: z.string(),
  appointmentDate: z.string(),
  state: z.literal("california"),
  executor: executorSchema,
  assets: z.array(assetSchema),
  debts: z.array(debtSchema),
  beneficiaries: z.array(beneficiarySchema),
  documents: z.array(uploadedDocumentSchema),
  tasks: z.array(taskSchema),
  alerts: z.array(alertSchema),
  phase: estatePhaseSchema,
  createdAt: z.string(),
  updatedAt: z.string(),
}).strict();
