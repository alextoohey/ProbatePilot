import type { Alert, AlertTimingStatus } from "@/types/estate";

const TIMING_LABELS: Record<Exclude<AlertTimingStatus, "dated">, string> = {
  blocking: "Blocking",
  prerequisite: "Prerequisite",
  missing_data: "Missing data",
  no_deadline: "No fixed deadline",
};

export function formatAlertTimingLabel(alert: Pick<Alert, "daysRemaining" | "timingStatus">): string {
  if (typeof alert.daysRemaining === "number") {
    const days = alert.daysRemaining;
    if (days < 0) {
      const overdue = Math.abs(days);
      return `Overdue by ${overdue} day${overdue === 1 ? "" : "s"}`;
    }
    if (days === 0) return "Due today";
    return `Due in ${days} day${days === 1 ? "" : "s"}`;
  }

  const status = alert.timingStatus ?? "no_deadline";
  if (status === "dated") {
    return TIMING_LABELS.no_deadline;
  }

  return TIMING_LABELS[status];
}
