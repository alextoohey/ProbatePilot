import type { Asset, Beneficiary, Debt } from "./estate";

export type DocumentType = "will" | "bank_statement" | "deed" | "creditor_notice" | "unknown";

export interface DocumentExtraction {
  documentType: DocumentType;
  confidence: number;
  rawChunks: string[];
}

export interface WillExtraction extends DocumentExtraction {
  documentType: "will";
  executorName?: string | null;
  beneficiaries: Beneficiary[];
  assets: Asset[];
  trustClauses: string[];
  specialInstructions: string[];
  codicils: string[];
}

export interface BankStatementExtraction extends DocumentExtraction {
  documentType: "bank_statement";
  institution?: string | null;
  accountLast4?: string | null;
  accountType?: string | null;
  balance?: number | null;
  statementDate?: string | null;
  notableTransactions: string[];
}

export interface DeedExtraction extends DocumentExtraction {
  documentType: "deed";
  propertyAddress?: string | null;
  apn?: string | null;
  legalDescription?: string | null;
  grantor?: string | null;
  grantee?: string | null;
  recordedDate?: string | null;
  estimatedValue?: number | null;
}

export interface CreditorNoticeExtraction extends DocumentExtraction {
  documentType: "creditor_notice";
  creditorName?: string | null;
  amountOwed?: number | null;
  accountNumber?: string | null;
  debtType: "secured" | "unsecured" | "priority";
  debts: Debt[];
}

export interface UnknownDocumentExtraction extends DocumentExtraction {
  documentType: "unknown";
  reason: string;
}

export type AnyDocumentExtraction =
  | WillExtraction
  | BankStatementExtraction
  | DeedExtraction
  | CreditorNoticeExtraction
  | UnknownDocumentExtraction;
