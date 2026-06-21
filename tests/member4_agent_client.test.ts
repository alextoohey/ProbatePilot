import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  generateLetter,
  getEstate,
  openChatStream,
  parseDocument,
  runDeadlineAgent,
  seedEstate,
} from "../web/lib/agentClient";
import type { Alert, EstateState } from "../web/types";

const alert: Alert = {
  id: "alert-creditors",
  severity: "critical",
  type: "deadline",
  title: "Known creditors have not been notified",
  body: "Send creditor notices.",
  rule: "CA Probate Code 9051",
  daysRemaining: 9,
  actionRequired: "Send certified notices.",
  createdAt: "2026-06-20T00:00:00.000Z",
  dismissed: false,
};

const estate: EstateState = {
  id: "demo-milligan",
  deceasedName: "Robert A. Milligan",
  dateOfDeath: "2026-06-03",
  appointmentDate: "2026-06-10",
  state: "california",
  executor: { name: "Dana Milligan", email: "dana@demo.com" },
  assets: [
    {
      id: "asset-bank-4412",
      type: "bank_account",
      description: "Wells Fargo account ending 4412 (checking)",
      estimatedValue: 38240,
      appraised: false,
      appraisedValue: null,
      beneficiaryNamed: null,
    },
  ],
  debts: [],
  beneficiaries: [],
  documents: [
    {
      id: "doc-bank",
      fileName: "checking.txt",
      documentType: "bank_statement",
      uploadedAt: "2026-06-20T00:00:00.000Z",
      source: null,
    },
  ],
  tasks: [],
  alerts: [alert],
  phase: 2,
  createdAt: "2026-06-20T00:00:00.000Z",
  updatedAt: "2026-06-20T00:00:00.000Z",
};

type FetchCall = {
  input: string | URL | Request;
  init?: RequestInit;
};

const calls: FetchCall[] = [];
const queuedPayloads: unknown[] = [];
let queuedBody: ReadableStream<Uint8Array> | null = null;

const originalFetch = globalThis.fetch;

globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
  calls.push({ input, init });
  const payload = queuedPayloads.shift();
  return {
    ok: true,
    status: 200,
    body: queuedBody,
    json: async () => payload,
  } as Response;
}) as typeof fetch;

function resetFetch(payloads: unknown[] = []) {
  calls.length = 0;
  queuedPayloads.length = 0;
  queuedPayloads.push(...payloads);
  queuedBody = null;
}

async function main() {
  resetFetch([{ estate, alerts: [alert] }]);
  const seeded = await seedEstate();
  assert.equal(calls[0].input, "/api/agent/seed");
  assert.equal(calls[0].init?.method, "POST");
  assert.equal(seeded.estate.id, "demo-milligan");
  assert.equal(seeded.alerts[0].id, "alert-creditors");

  resetFetch([{ estate }]);
  const loaded = await getEstate("estate-123");
  assert.equal(calls[0].input, "/api/agent/estate/estate-123");
  assert.equal(loaded.assets[0].description, "Wells Fargo account ending 4412 (checking)");

  resetFetch([{ estateId: "estate-123", alerts: [alert] }]);
  const alerts = await runDeadlineAgent("estate-123");
  assert.equal(calls[0].input, "/api/agent/deadline-agent");
  assert.equal(calls[0].init?.method, "POST");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { estateId: "estate-123" });
  assert.equal(alerts[0].severity, "critical");

  resetFetch([
    {
      estateId: "estate-123",
      extraction: {
        documentType: "bank_statement",
        confidence: 0.8,
        institution: "Wells Fargo",
        accountLast4: "4412",
        accountType: "checking",
        balance: 38240,
        statementDate: null,
        notableTransactions: [],
        rawChunks: ["Wells Fargo checking statement account 4412."],
      },
      alerts: [alert],
    },
  ]);
  const parsed = await parseDocument(new File(["checking account"], "checking.txt", { type: "text/plain" }), "estate-123");
  assert.equal(calls[0].input, "/api/agent/parse-document");
  assert.equal(calls[0].init?.method, "POST");
  assert.ok(calls[0].init?.body instanceof FormData);
  assert.equal((calls[0].init?.body as FormData).get("estateId"), "estate-123");
  assert.equal(((calls[0].init?.body as FormData).get("file") as File).name, "checking.txt");
  assert.equal(parsed.extraction.documentType, "bank_statement");

  resetFetch([{ estateId: "estate-123", letterType: "creditor_notice", draft: "Draft letter" }]);
  const letter = await generateLetter("creditor_notice", "estate-123");
  assert.equal(calls[0].input, "/api/agent/generate-letter");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), {
    estateId: "estate-123",
    letterType: "creditor_notice",
  });
  assert.equal(letter.draft, "Draft letter");

  queuedBody = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: {"token":"ok"}\n\n'));
      controller.close();
    },
  });
  resetFetch([]);
  queuedBody = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: {"token":"ok"}\n\n'));
      controller.close();
    },
  });
  const stream = await openChatStream({ estateId: "estate-123", message: "What next?", topK: 3 });
  assert.equal(calls[0].input, "/api/agent/chat");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), {
    estateId: "estate-123",
    message: "What next?",
    topK: 3,
  });
  assert.ok(stream);

  resetFetch([
    {
      estateId: "estate-123",
      extraction: {
        documentType: "bank_statement",
        confidence: 0.8,
        rawChunks: [],
      },
      alerts: [],
    },
  ]);
  await assert.rejects(
    () => parseDocument(new File(["bad"], "bad.txt", { type: "text/plain" }), "estate-123"),
    /Required/,
  );

  const uploadScreenSource = readFileSync(
    join(__dirname, "../../../web/components/screens/UploadScreen.tsx"),
    "utf8",
  );
  assert.match(uploadScreenSource, /parseDocument/);
  assert.match(uploadScreenSource, /getEstate/);
  assert.doesNotMatch(uploadScreenSource, /function fakeUpload/);

  console.log("member4 agent client integration tests passed");
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => {
    globalThis.fetch = originalFetch;
  });
