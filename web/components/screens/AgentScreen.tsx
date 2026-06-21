"use client";
// Agent command center. Unlike the dashboard (which lists only the alerts that
// fired), this is a compliance ledger over the ENTIRE California probate rule
// set: it shows every rule the agent checked, the ones that passed, and the
// statutory context (trigger, deadline, consequence) behind each finding.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Badge, Button, Card } from "@/components/ds";
import { formatAlertTimingLabel } from "@/lib/alertTiming";
import { type EstateProfile, type Alert as DesignAlert } from "@/lib/design/data";
import { CALIFORNIA_PROBATE_RULES, RULE_COUNT, ruleIdFromAlert, type ProbateRule } from "@/lib/probateRules";
import type { Alert as BackendAlert, EstateState } from "@/types";

type Props = {
  estate?: EstateProfile;
  alerts: DesignAlert[];
  completedIds?: string[];
  liveEstate?: EstateState | null;
  liveAlertsFailed?: boolean;
  rerunning?: boolean;
  completingId?: string | null;
  onOpenStep?: (id: string) => void;
  onComplete?: (id: string) => Promise<void> | void;
  onRerun?: () => void;
};

const SEVERITY_ORDER: Record<DesignAlert["severity"], number> = { critical: 0, warning: 1, info: 2 };

type RuleStatus = "flagged" | "resolved" | "compliant";
type LedgerRow = {
  rule: ProbateRule;
  status: RuleStatus;
  primary: DesignAlert | null; // worst open alert, for flagged rules
};

function isResolved(alert: DesignAlert, done: Set<string>): boolean {
  return done.has(alert.id) || Boolean((alert as BackendAlert).dismissed);
}

export function AgentScreen({
  estate,
  alerts,
  completedIds = [],
  liveEstate,
  liveAlertsFailed = false,
  rerunning = false,
  completingId = null,
  onOpenStep,
  onComplete,
  onRerun,
}: Props) {
  const I = ExecutorIcons;
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());
  const done = new Set(completedIds);

  // Bucket every alert under the rule that produced it.
  const byRule = new Map<string, DesignAlert[]>();
  for (const alert of alerts) {
    const ruleId = ruleIdFromAlert(alert);
    if (!ruleId) continue;
    const bucket = byRule.get(ruleId);
    if (bucket) bucket.push(alert);
    else byRule.set(ruleId, [alert]);
  }

  const rows: LedgerRow[] = CALIFORNIA_PROBATE_RULES.map((rule) => {
    const ruleAlerts = byRule.get(rule.id) ?? [];
    const openAlerts = ruleAlerts
      .filter((a) => !isResolved(a, done))
      .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
    const status: RuleStatus = openAlerts.length ? "flagged" : ruleAlerts.length ? "resolved" : "compliant";
    return { rule, status, primary: openAlerts[0] ?? null };
  });

  const flagged = rows
    .filter((r) => r.status === "flagged")
    .sort((a, b) => SEVERITY_ORDER[a.primary!.severity] - SEVERITY_ORDER[b.primary!.severity]
      || (a.primary!.daysRemaining ?? Infinity) - (b.primary!.daysRemaining ?? Infinity));
  const compliant = rows.filter((r) => r.status === "compliant");
  const resolved = rows.filter((r) => r.status === "resolved");

  const nextDeadline = flagged
    .map((r) => r.primary!.daysRemaining)
    .filter((d): d is number => typeof d === "number")
    .sort((a, b) => a - b)[0];

  const deceasedName = liveEstate?.deceasedName ?? estate?.deceasedName ?? "this estate";

  function toggle(id: string) {
    setExpanded((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "36px 40px", display: "grid", gap: "var(--space-8)" }}>
      <header style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-6)" }}>
        <div>
          <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>DeadlineAgent</p>
          <h1 style={{ margin: "8px 0 0", display: "flex", alignItems: "center", gap: 10, fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>
            <span style={{ display: "inline-flex", color: "var(--evergreen-600)" }}><I.Sparkle size={26} /></span>
            Compliance ledger
          </h1>
          <p style={{ margin: "8px 0 0", maxWidth: 640, fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
            Every California probate rule the agent checked against the estate of {deceasedName} — what it flagged, and the {compliant.length} {compliant.length === 1 ? "rule" : "rules"} you're currently clear on.
          </p>
        </div>
        <Button variant="secondary" leadingIcon={<I.Sparkle size={16} />} onClick={onRerun} disabled={rerunning} style={{ flex: "none" }}>
          {rerunning ? "Re-checking…" : "Re-run agent"}
        </Button>
      </header>

      <Card padded>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-5)" }}>
          <StatCell label="Rules checked" value={String(RULE_COUNT)} tone="neutral" />
          <StatCell label="Flagged" value={String(flagged.length)} tone={flagged.length ? "critical" : "neutral"} />
          <StatCell label="Compliant" value={String(compliant.length)} tone="success" />
          <StatCell
            label="Next deadline"
            value={typeof nextDeadline === "number" ? `${nextDeadline}d` : flagged.length ? "—" : "Clear"}
            tone={typeof nextDeadline === "number" && nextDeadline <= 14 ? "critical" : "neutral"}
          />
        </div>
        <p style={{ margin: "var(--space-4) 0 0", fontSize: "var(--text-xs)", color: "var(--text-subtle)" }}>
          Claude reasons over the deterministic California probate rules engine on every run and ranks findings by severity, urgency, and executor liability.
        </p>
      </Card>

      {liveAlertsFailed ? (
        <Card tint padded>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--warning-text)" }}>
            <I.Bell size={18} color="var(--warning-accent)" />
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>The agent couldn't be reached. Start the Python agent and re-run.</span>
          </div>
        </Card>
      ) : null}

      <section>
        <h2 style={{ margin: "0 0 var(--space-2)", fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--text-strong)" }}>
          {flagged.length ? "Rules the agent flagged" : "No rules flagged"}
        </h2>
        <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
          {flagged.length
            ? "Ranked by severity, then by how soon the statutory deadline falls. Expand any rule for the agent's finding and the statute behind it."
            : "The agent ran every rule and found nothing outstanding for this estate."}
        </p>

        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {flagged.map((row) => (
            <FlaggedRuleCard
              key={row.rule.id}
              row={row}
              expanded={expanded.has(row.rule.id)}
              completing={completingId === row.primary!.id}
              onToggle={() => toggle(row.rule.id)}
              onOpenStep={onOpenStep}
              onComplete={onComplete}
            />
          ))}
          {flagged.length === 0 && !liveAlertsFailed ? (
            <Card tint padded>
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--success-text)" }}>
                <I.CheckCircle size={20} color="var(--success-accent)" />
                <span style={{ fontWeight: 600 }}>All {RULE_COUNT} rules are clear. The agent will flag the next one the moment it trips.</span>
              </div>
            </Card>
          ) : null}
        </div>
      </section>

      {compliant.length || resolved.length ? (
        <Card title="Rules you're clear on" subtitle="Checked on the last run and currently compliant" padded={false}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {resolved.map((row, i) => (
              <RuleLedgerRow key={row.rule.id} rule={row.rule} resolved first={i === 0} />
            ))}
            {compliant.map((row, i) => (
              <RuleLedgerRow key={row.rule.id} rule={row.rule} first={i === 0 && resolved.length === 0} />
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}

function StatCell({ label, value, tone }: { label: string; value: string; tone: "critical" | "warning" | "success" | "neutral" }) {
  const color =
    tone === "critical" ? "var(--critical-text)" :
    tone === "warning" ? "var(--warning-text)" :
    tone === "success" ? "var(--success-text)" :
    "var(--text-strong)";
  return (
    <div>
      <div style={{ fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>{label}</div>
      <div style={{ marginTop: 6, fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

function FlaggedRuleCard({
  row,
  expanded,
  completing,
  onToggle,
  onOpenStep,
  onComplete,
}: {
  row: LedgerRow;
  expanded: boolean;
  completing: boolean;
  onToggle: () => void;
  onOpenStep?: (id: string) => void;
  onComplete?: (id: string) => Promise<void> | void;
}) {
  const I = ExecutorIcons;
  const alert = row.primary!;
  const { rule } = row;
  const tones: Record<DesignAlert["severity"], { bd: string; fg: string; ac: string }> = {
    critical: { bd: "var(--critical-border)", fg: "var(--critical-text)", ac: "var(--critical-accent)" },
    warning: { bd: "var(--warning-border)", fg: "var(--warning-text)", ac: "var(--warning-accent)" },
    info: { bd: "var(--info-border)", fg: "var(--info-text)", ac: "var(--info-accent)" },
  };
  const t = tones[alert.severity] ?? tones.info;

  return (
    <article
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
        borderLeft: `3px solid ${t.ac}`,
        borderRadius: "var(--radius-md)",
        padding: "var(--space-4) var(--space-5)",
        fontFamily: "var(--font-sans)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Badge tone={alert.severity} dot>{alert.severity}</Badge>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600, color: t.fg, border: `1px solid ${t.bd}`, borderRadius: "var(--radius-full)", padding: "2px 9px", whiteSpace: "nowrap" }}>
          {formatAlertTimingLabel(alert)}
        </span>
        <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--text-subtle)" }}>{rule.statute}</span>
      </div>

      <h3 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-lg)", fontWeight: 600, color: "var(--text-strong)", lineHeight: "var(--leading-snug)" }}>
        {alert.title}
      </h3>

      {alert.actionRequired ? (
        <p style={{ margin: "10px 0 0", fontSize: "var(--text-sm)", color: "var(--text-strong)" }}>
          <strong style={{ fontWeight: 600 }}>Next action:</strong> {alert.actionRequired}
        </p>
      ) : null}

      <button
        onClick={onToggle}
        aria-expanded={expanded}
        style={{ marginTop: 12, display: "inline-flex", alignItems: "center", gap: 6, border: "none", background: "transparent", cursor: "pointer", padding: 0, color: "var(--text-brand)", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 600 }}
      >
        <span style={{ display: "inline-flex", transform: expanded ? "rotate(90deg)" : "none", transition: "transform var(--transition-fast)" }}>
          <I.ChevronRight size={15} />
        </span>
        {expanded ? "Hide the agent's finding" : "Show the agent's finding"}
      </button>

      {expanded ? (
        <div style={{ marginTop: 12, padding: "var(--space-4)", background: "var(--surface-sunken)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", display: "grid", gap: "var(--space-3)" }}>
          <ReasonRow label="Rule">{`${rule.title} (${rule.statute})`}</ReasonRow>
          <ReasonRow label="Triggered by">{rule.trigger}</ReasonRow>
          <ReasonRow label="Statutory window">{rule.deadline}</ReasonRow>
          <ReasonRow label="Finding">{alert.body}</ReasonRow>
          <ReasonRow label="If ignored" danger>{rule.consequence}</ReasonRow>
        </div>
      ) : null}

      <div style={{ marginTop: "var(--space-4)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <Button variant="primary" size="sm" trailingIcon={<I.ChevronRight size={14} />} onClick={() => onOpenStep && onOpenStep(alert.id)}>
          View steps
        </Button>
        {onComplete ? (
          <Button variant="secondary" size="sm" leadingIcon={<I.Check size={14} />} onClick={() => onComplete(alert.id)} disabled={completing}>
            {completing ? "Marking…" : "Mark complete"}
          </Button>
        ) : null}
      </div>
    </article>
  );
}

function RuleLedgerRow({ rule, resolved = false, first = false }: { rule: ProbateRule; resolved?: boolean; first?: boolean }) {
  const I = ExecutorIcons;
  return (
    <li style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderTop: first ? "none" : "1px solid var(--border-subtle)" }}>
      <span style={{ flex: "none", display: "inline-flex", color: "var(--success-accent)" }}><I.CheckCircle size={18} /></span>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{rule.title}</span>
        <span style={{ display: "block", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{rule.statute} · {rule.deadline}</span>
      </span>
      <Badge tone={resolved ? "neutral" : "success"}>{resolved ? "Resolved" : "Compliant"}</Badge>
    </li>
  );
}

function ReasonRow({ label, children, danger = false }: { label: string; children: React.ReactNode; danger?: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: "var(--space-3)", alignItems: "baseline" }}>
      <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-subtle)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", lineHeight: "var(--leading-relaxed)", color: danger ? "var(--critical-text)" : "var(--text-body)" }}>
        {children || "—"}
      </span>
    </div>
  );
}
