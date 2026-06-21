import assert from "node:assert/strict";

import {
  chatRequestSchema,
  deadlineAgentResponseSchema,
  parseDocumentResponseSchema,
  searchResultSchema,
  seedResponseSchema,
} from "../web/lib/schemas/api";
import { documentExtractionSchema } from "../web/lib/schemas/documents";
import { estateStateSchema } from "../web/lib/schemas/estate";
import type {
  Alert,
  EstateState,
  ParseDocumentResponse,
  SearchResult,
} from "../web/types";

const alert: Alert = {
  id: "alert-inventory",
  severity: "critical",
  type: "deadline",
  title: "Inventory due soon",
  body: "File DE-160 before the deadline.",
  rule: "CA Probate Code inventory",
  daysRemaining: 9,
  actionRequired: "Prepare inventory and appraisal.",
  createdAt: "2026-06-20T00:00:00.000Z",
  dismissed: false,
};

const estate: EstateState = {
  id: "demo-milligan",
  deceasedName: "Robert A. Milligan",
  dateOfDeath: "2026-06-03",
  appointmentDate: "2026-06-10",
  state: "california",
  executor: {
    name: "Dana Milligan",
    email: "dana@demo.com",
  },
  assets: [
    {
      id: "asset-home",
      type: "real_estate",
      description: "1847 Marin Ave, Berkeley CA",
      estimatedValue: 220000,
      appraised: false,
      appraisedValue: null,
      beneficiaryNamed: null,
    },
  ],
  debts: [
    {
      id: "debt-ucsf",
      creditor: "UCSF Medical Center",
      amount: 4200,
      type: "unsecured",
      notified: false,
      notifiedDate: null,
      claimFiled: null,
    },
  ],
  beneficiaries: [
    {
      id: "beneficiary-dana",
      name: "Dana Milligan",
      share: "40%",
      specificBequest: null,
      contactInfo: null,
    },
  ],
  documents: [
    {
      id: "doc-will",
      fileName: "will.txt",
      documentType: "will",
      uploadedAt: "2026-06-20T00:00:00.000Z",
      source: null,
    },
  ],
  tasks: [
    {
      id: "task-inventory",
      title: "Prepare DE-160 Inventory and Appraisal",
      status: "todo",
      phase: 2,
      dueDate: null,
      relatedAlertId: null,
    },
  ],
  alerts: [alert],
  phase: 2,
  createdAt: "2026-06-20T00:00:00.000Z",
  updatedAt: "2026-06-20T00:00:00.000Z",
};

const searchResult: SearchResult = {
  text: "The will names Dana as executor.",
  score: 0.98,
  source: "will.txt",
  documentType: "will",
  chunkIndex: 0,
  estateId: "demo-milligan",
};

const parseResponse: ParseDocumentResponse = {
  estateId: "demo-milligan",
  extraction: {
    documentType: "will",
    confidence: 0.9,
    executorName: "Dana Milligan",
    beneficiaries: estate.beneficiaries,
    assets: estate.assets,
    trustClauses: [],
    specialInstructions: ["Keep family photos together."],
    codicils: [],
    rawChunks: ["Dana Milligan shall serve as executor."],
  },
  documentType: "will",
  needsTypeSelection: false,
  alerts: [alert],
};

assert.equal(estateStateSchema.parse(estate).id, "demo-milligan");
assert.equal(seedResponseSchema.parse({ estate, alerts: [alert] }).alerts.length, 1);
assert.equal(deadlineAgentResponseSchema.parse({ estateId: estate.id, alerts: [alert] }).estateId, estate.id);
assert.equal(searchResultSchema.parse(searchResult).source, "will.txt");
assert.equal(parseDocumentResponseSchema.parse(parseResponse).extraction.documentType, "will");
assert.equal(chatRequestSchema.parse({ estateId: estate.id, message: "What is next?" }).topK, undefined);
assert.equal(chatRequestSchema.parse({ estateId: estate.id, message: "What is next?", topK: 3 }).topK, 3);

assert.equal(
  documentExtractionSchema.parse({
    documentType: "bank_statement",
    confidence: 0.7,
    institution: "Wells Fargo",
    accountLast4: "4412",
    accountType: "checking",
    balance: 38240,
    statementDate: "2026-06-01",
    notableTransactions: [],
    rawChunks: ["Checking account ending 4412."],
  }).documentType,
  "bank_statement",
);

assert.throws(() => estateStateSchema.parse({ ...estate, extra: true }));
assert.throws(() => estateStateSchema.parse({ ...estate, phase: 7 }));
assert.throws(() => documentExtractionSchema.parse({ documentType: "will", confidence: 2, rawChunks: [] }));
assert.throws(() => searchResultSchema.parse({ ...searchResult, estateId: undefined }));

console.log("member2 web contract tests passed");
