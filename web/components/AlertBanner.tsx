import type { Alert } from "@/types/estate";
import { formatAlertTimingLabel } from "@/lib/alertTiming";

const tone = {
  critical: "border-red-300 bg-red-50 text-red-950",
  warning: "border-amber-300 bg-amber-50 text-amber-950",
  info: "border-sky-300 bg-sky-50 text-sky-950",
};

export function AlertBanner({ alert }: { alert: Alert }) {
  return (
    <article className={`rounded-md border p-4 ${tone[alert.severity]}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide">{alert.severity}</p>
          <h2 className="mt-1 text-lg font-semibold">{alert.title}</h2>
        </div>
        <span className="shrink-0 rounded border border-current px-2 py-1 text-sm">
          {formatAlertTimingLabel(alert)}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6">{alert.body}</p>
      <p className="mt-3 text-sm font-semibold">Next action: {alert.actionRequired}</p>
    </article>
  );
}

