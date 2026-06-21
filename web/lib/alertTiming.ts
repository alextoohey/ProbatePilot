import type { Alert, AlertTimingStatus } from "@/types/estate";

const TIMING_LABELS: Record<Exclude<AlertTimingStatus, "dated">, string> = {
  blocking: "Blocking",
  prerequisite: "Prerequisite",
  missing_data: "Missing data",
  no_deadline: "No fixed deadline",
};

export function formatAlertTimingLabel(alert: Pick<Alert, "daysRemaining" | "timingStatus">): string {
  if (typeof alert.daysRemaining === "number") {
    return `${alert.daysRemaining} days`;
  }

  const status = alert.timingStatus ?? "no_deadline";
  if (status === "dated") {
    return TIMING_LABELS.no_deadline;
  }

  return TIMING_LABELS[status];
}
