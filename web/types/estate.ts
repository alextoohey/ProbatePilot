export type AssetType =
  | "real_estate"
  | "bank_account"
  | "retirement"
  | "vehicle"
  | "personal_property"
  | "other";

export type AlertSeverity = "critical" | "warning" | "info";
export type AlertType = "deadline" | "liability" | "missing_doc" | "rule_violation";
export type AlertTimingStatus = "dated" | "blocking" | "prerequisite" | "missing_data" | "no_deadline";
export type EstatePhase = 1 | 2 | 3 | 4 | 5 | 6;
export type TaskStatus = "todo" | "in_progress" | "done" | "blocked";

export interface Executor {
  name: string;
  email: string;
}

export interface Asset {
  id: string;
  type: AssetType;
  description: string;
  estimatedValue?: number | null;
  appraised: boolean;
  appraisedValue?: number | null;
  beneficiaryNamed?: boolean | null;
}

export interface Debt {
  id: string;
  creditor: string;
  amount: number;
  type: "secured" | "unsecured" | "priority";
  notified: boolean;
  notifiedDate?: string | null;
  claimFiled?: boolean | null;
}

export interface Beneficiary {
  id: string;
  name: string;
  share?: string | null;
  specificBequest?: string | null;
  contactInfo?: string | null;
}

export interface UploadedDocument {
  id: string;
  fileName: string;
  documentType: string;
  uploadedAt: string;
  source?: string | null;
}

export interface Task {
  id: string;
  title: string;
  status: TaskStatus;
  phase: EstatePhase;
  dueDate?: string | null;
  relatedAlertId?: string | null;
}

export interface Alert {
  id: string;
  severity: AlertSeverity;
  type: AlertType;
  title: string;
  body: string;
  rule: string;
  daysRemaining?: number | null;
  timingStatus?: AlertTimingStatus;
  actionRequired: string;
  whatYouNeed: string[];
  steps: string[];
  createdAt: string;
  dismissed: boolean;
}

export interface SavedLetter {
  id: string;
  letterType: string;
  recipientName?: string | null;
  draft: string;
  savedAt: string;
}

export interface EstateState {
  id: string;
  deceasedName: string;
  dateOfDeath: string;
  appointmentDate: string;
  state: "california";
  county?: string | null;
  executor: Executor;
  assets: Asset[];
  debts: Debt[];
  beneficiaries: Beneficiary[];
  documents: UploadedDocument[];
  tasks: Task[];
  alerts: Alert[];
  letters: SavedLetter[];
  phase: EstatePhase;
  createdAt: string;
  updatedAt: string;
}
