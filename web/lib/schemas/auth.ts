import { z } from "zod";
import { estateStateSchema } from "./estate";

export const publicUserSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string(),
  phone: z.string().nullable().optional(),
  relationship: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  county: z.string().nullable().optional(),
  estateIds: z.array(z.string()),
  createdAt: z.string(),
}).strict();

export const registerRequestSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  password: z.string().min(8),
  phone: z.string().nullable().optional(),
  deceasedName: z.string().min(1),
  dateOfDeath: z.string().nullable().optional(),
  relationship: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  county: z.string().nullable().optional(),
  hasWill: z.string().nullable().optional(),
}).strict();

export const loginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
}).strict();

export const authResponseSchema = z.object({
  token: z.string(),
  user: publicUserSchema,
  estate: estateStateSchema.nullable().optional(),
}).strict();

export const meResponseSchema = z.object({
  user: publicUserSchema,
  estates: z.array(estateStateSchema),
}).strict();
