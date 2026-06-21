// California probate rule catalog, mirrored from
// agent/rules/california_probate.py (CALIFORNIA_PROBATE_RULES). The agent
// evaluates every rule here on each run; the dashboard only renders the ones
// that fire. The Agent command center uses the full catalog to show a
// compliance ledger — including the rules that PASSED, which is information the
// estate alert list never carries.
import type { Alert } from "@/types";

export type ProbateRule = {
  id: string;
  title: string;
  statute: string;
  /** Estate fact that triggers evaluation. */
  trigger: string;
  /** Statutory window once triggered. */
  deadline: string;
  /** What goes wrong if it is missed. */
  consequence: string;
};

export const CALIFORNIA_PROBATE_RULES: ProbateRule[] = [
  { id: "de-140", title: "DE-140 Probate Petition", statute: "CA Probate Code", trigger: "Date of death", deadline: "File ASAP", consequence: "No legal authority to act until filed" },
  { id: "death-certificates", title: "Certified death certificates", statute: "Operational requirement", trigger: "Date of death", deadline: "Immediately", consequence: "Institutions require certified copies" },
  { id: "de-160", title: "DE-160 Inventory & Appraisal", statute: "CA Probate Code", trigger: "Appointment date", deadline: "Within 4 months", consequence: "Court sanctions and personal liability" },
  { id: "creditor-notice", title: "Creditor notification", statute: "CA Probate Code §9051", trigger: "Appointment date", deadline: "Within 30 days", consequence: "Personal liability for late distributions" },
  { id: "newspaper-notice", title: "Newspaper notice to creditors", statute: "CA Probate Code §9052", trigger: "First publication date", deadline: "Over 3 weeks", consequence: "Defective notice to creditors" },
  { id: "claim-period", title: "Creditor claim period", statute: "CA Probate Code", trigger: "First publication date", deadline: "Closes at 4 months", consequence: "Cannot distribute before it closes" },
  { id: "estate-ein", title: "Estate EIN", statute: "IRS SS-4", trigger: "Estate banking activity", deadline: "Before banking", consequence: "Cannot open an estate bank account" },
  { id: "final-1040", title: "Final personal 1040", statute: "IRS", trigger: "Date of death", deadline: "April 15 following year", consequence: "IRS penalties" },
  { id: "form-1041", title: "Estate Form 1041", statute: "IRS", trigger: "Estate income over $600", deadline: "April 15 following year", consequence: "IRS penalties" },
  { id: "debt-order", title: "Debt payment order", statute: "CA Probate Code", trigger: "Before distribution", deadline: "Secured → unsecured → distributions", consequence: "Out-of-order payments create personal liability" },
  { id: "appraisal-needed", title: "Property appraisal", statute: "CA Probate Code", trigger: "Before DE-160", deadline: "Before filing DE-160", consequence: "Blocks the inventory filing" },
];

export const RULE_COUNT = CALIFORNIA_PROBATE_RULES.length;

/**
 * Recover the rule id from an alert. The agent formats `alert.rule` as
 * `"{id}: {title} ({statute})"` (see california_probate._alert), so the id is
 * the text before the first colon.
 */
export function ruleIdFromAlert(alert: Pick<Alert, "rule">): string | null {
  if (!alert.rule) return null;
  const head = alert.rule.split(":")[0]?.trim();
  return head ? head : null;
}
