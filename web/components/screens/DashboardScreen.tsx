"use client";
// Dashboard, estate overview, the DeadlineAgent's ranked alerts, and tasks.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Card, Alert, Badge, ProgressSteps, Button, Avatar } from "@/components/ds";
import { DEMO_ESTATE, fmtMoney, type EstateProfile, type Beneficiary } from "@/lib/design/data";
import { getEstate } from "@/lib/agentClient";
import type { EstateState } from "@/types";
import { BeneficiaryModal } from "./BeneficiaryModal";

// Generic CA probate phases, used to label the phase rail for real estates.
const PROBATE_PHASES = DEMO_ESTATE.phases;

function formatLongDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

type Props = {
  estate?: EstateProfile;
  completedIds?: string[];
  onOpenStep?: (id: string) => void;
  onGoDocuments?: () => void;
};

type MetricTone = "neutral" | "brand" | "critical" | "success";

function MetricTile({
  label,
  value,
  detail,
  tone = "neutral",
  progress,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  detail: React.ReactNode;
  tone?: MetricTone;
  progress?: { value: number; max: number; label: string };
}) {
  const tones: Record<MetricTone, { value: string; accent: string; track: string; bg: string }> = {
    neutral: { value: "var(--text-strong)", accent: "var(--ink-500)", track: "rgba(148, 163, 184, 0.18)", bg: "rgba(255, 255, 255, 0.74)" },
    brand: { value: "var(--text-brand)", accent: "var(--evergreen-600)", track: "rgba(60, 129, 89, 0.14)", bg: "rgba(255, 255, 255, 0.78)" },
    critical: { value: "var(--critical-text)", accent: "var(--critical-accent)", track: "rgba(220, 38, 38, 0.12)", bg: "rgba(255, 255, 255, 0.78)" },
    success: { value: "var(--success-text)", accent: "var(--success-accent)", track: "rgba(60, 129, 89, 0.14)", bg: "rgba(255, 255, 255, 0.78)" },
  };
  const t = tones[tone];
  const pct = progress ? Math.max(0, Math.min(100, progress.max ? (progress.value / progress.max) * 100 : 0)) : 0;

  return (
    <div
      style={{
        minWidth: 0,
        display: "grid",
        gap: 12,
        padding: 16,
        border: "1px solid rgba(203, 213, 225, 0.66)",
        borderRadius: 8,
        background: t.bg,
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
      }}
    >
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 12, alignItems: "start" }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>
            {label}
          </p>
          <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {detail}
          </p>
        </div>
        <strong style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-xl)", fontWeight: 700, lineHeight: 1, color: t.value, whiteSpace: "nowrap", letterSpacing: 0 }}>
          {value}
        </strong>
      </div>
      {progress ? (
        <div>
          <div style={{ height: 6, borderRadius: "var(--radius-full)", background: t.track, overflow: "hidden" }}>
            <span style={{ display: "block", width: `${pct}%`, height: "100%", borderRadius: "inherit", background: t.accent }} />
          </div>
          <p style={{ margin: "6px 0 0", fontSize: "var(--text-xs)", color: "var(--text-subtle)" }}>{progress.label}</p>
        </div>
      ) : null}
    </div>
  );
}

function PhaseRail({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div style={{ overflowX: "auto", paddingBottom: 2 }}>
      <ol style={{ display: "grid", gridTemplateColumns: `repeat(${steps.length}, minmax(112px, 1fr))`, gap: 8, listStyle: "none", margin: 0, padding: 0, minWidth: 680 }}>
        {steps.map((label, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li
              key={label}
              style={{
                display: "grid",
                gap: 7,
                padding: "11px 12px",
                border: `1px solid ${active ? "rgba(36, 80, 56, 0.26)" : done ? "rgba(60, 129, 89, 0.18)" : "rgba(203, 213, 225, 0.58)"}`,
                borderRadius: 8,
                background: active ? "rgba(227, 239, 231, 0.78)" : done ? "rgba(255, 255, 255, 0.72)" : "rgba(255, 255, 255, 0.48)",
                boxShadow: active ? "0 1px 2px rgba(15, 23, 42, 0.06)" : "none",
              }}
            >
              <span style={{ width: 22, height: 22, display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--radius-full)", background: active ? "var(--evergreen-700)" : done ? "var(--evergreen-100)" : "rgba(148, 163, 184, 0.14)", color: active ? "var(--text-inverse)" : done ? "var(--text-brand)" : "var(--text-subtle)", fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700 }}>
                {i + 1}
              </span>
              <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: active ? 700 : 500, lineHeight: 1.25, color: active ? "var(--text-strong)" : done ? "var(--text-muted)" : "var(--text-subtle)" }}>
                {label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function DashboardScreen({ estate, completedIds = [], onOpenStep, onGoDocuments }: Props) {
  const E = DEMO_ESTATE;
  const fmt = fmtMoney;
  const I = ExecutorIcons;
  const [benList, setBenList] = React.useState<Beneficiary[]>(E.beneficiaries.map((b) => ({ ...b })));
  const [openBenId, setOpenBenId] = React.useState<string | null>(null);

  // Real (non-demo) estates load their live state from the agent.
  const isReal = !!estate && !estate.seeded;
  const [real, setReal] = React.useState<EstateState | null>(null);
  const [loadingReal, setLoadingReal] = React.useState(isReal);

  React.useEffect(() => {
    if (!isReal || !estate) return;
    let cancelled = false;
    setLoadingReal(true);
    getEstate(estate.id)
      .then((e) => { if (!cancelled) setReal(e); })
      .catch(() => { if (!cancelled) setReal(null); })
      .finally(() => { if (!cancelled) setLoadingReal(false); });
    return () => { cancelled = true; };
  }, [isReal, estate]);

  if (isReal && estate) {
    if (loadingReal) {
      return (
        <div style={{ display: "flex", height: "100%", minHeight: 320, alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)" }}>
          Loading the estate…
        </div>
      );
    }
    // Once any document is on file, show the live estate instead of onboarding.
    if (real && real.documents.length > 0) {
      return <RealDashboard estate={estate} real={real} />;
    }
    return (
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "48px 40px", display: "grid", gap: "var(--space-8)" }}>
        <header>
          <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>New estate</p>
          <h1 style={{ margin: "8px 0 0", fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>
            Let's set up the estate of {estate.deceasedName}
          </h1>
          <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
            You're the {estate.role.toLowerCase()} for this {estate.state} estate in {estate.county} County. Add a few documents and Executor AI will build the estate and start tracking deadlines for you.
          </p>
        </header>
        <Card padded>
          <ProgressSteps current={0} steps={E.phases} />
        </Card>
        <Card tint padded>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
            <span style={{ flex: "none", width: 44, height: 44, borderRadius: "999px", background: "var(--evergreen-100)", color: "var(--evergreen-700)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
              <I.Upload size={20} />
            </span>
            <div style={{ flex: 1 }}>
              <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-lg)", fontWeight: 600, color: "var(--text-strong)" }}>Start with one document</h2>
              <p style={{ margin: "6px 0 14px", fontSize: "var(--text-sm)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)" }}>
                The will, the death certificate, or a recent bank statement is a great first upload. We'll take it from there.
              </p>
              <Button variant="primary" leadingIcon={<I.Upload size={16} />} onClick={onGoDocuments}>Add documents</Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const done = new Set(completedIds);
  const phase2 = E.alerts;
  const phase2Done = phase2.every((a) => done.has(a.id));
  const next = E.alertsNext || [];
  const nextDone = phase2Done && next.every((a) => done.has(a.id));

  // Once the current phase is cleared, the next phase's assignments appear.
  const activeAlerts = phase2Done ? next : phase2;
  const open = activeAlerts.filter((a) => !done.has(a.id));
  const completed = [...phase2, ...(phase2Done ? next : [])].filter((a) => done.has(a.id));
  const justAdvanced = phase2Done && open.length > 0;
  const assetTotal = E.assets.reduce((s, a) => s + a.value, 0);
  const debtTotal = E.debts.reduce((s, d) => s + d.amount, 0);

  const taskTone = { done: "success", todo: "neutral", blocked: "warning" } as const;
  const taskLabel = { done: "Done", todo: "To do", blocked: "Blocked" } as const;

  // When every attention item is handled, the estate advances to the next phase.
  const allDone = open.length === 0;
  const advanced = (phase2Done ? 1 : 0) + (nextDone ? 1 : 0);
  const currentIndex = Math.min(E.phase - 1 + advanced, E.phases.length - 1);
  const phaseNum = currentIndex + 1;
  const phaseName = E.phases[currentIndex];
  const nextPhaseName = E.phases[Math.min(currentIndex + 1, E.phases.length - 1)];
  const appraisedCount = E.assets.filter((a) => a.appraised).length;
  const notifiedCreditors = E.debts.filter((d) => d.notified).length;
  const beneficiaryNames = benList.map((b) => b.name.split(" ")[0]).join(", ");
  const netPosition = assetTotal - debtTotal;
  const leadingAlert = open[0];

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "36px 40px", display: "grid", gap: "var(--space-8)" }}>
      <header>
        <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Executor dashboard</p>
        <h1 style={{ margin: "8px 0 0", fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>
          The estate of {E.deceasedName}
        </h1>
        <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
          Letters testamentary issued {E.appointmentDate}. Here's where things stand, and the next thing to handle.
        </p>
      </header>

      <Card
        padded={false}
        style={{
          borderRadius: 8,
          borderColor: "rgba(203, 213, 225, 0.72)",
          background: "rgba(255, 255, 255, 0.72)",
          boxShadow: "0 18px 45px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.05)",
          backdropFilter: "blur(18px)",
          WebkitBackdropFilter: "blur(18px)",
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", background: "linear-gradient(135deg, rgba(255,255,255,0.94), rgba(241,247,243,0.62) 46%, rgba(240,249,255,0.58))" }}>
          <section style={{ padding: "24px 24px 22px", borderBottom: "1px solid rgba(203, 213, 225, 0.62)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                <span style={{ width: 42, height: 42, borderRadius: 8, display: "inline-flex", alignItems: "center", justifyContent: "center", background: "rgba(36, 80, 56, 0.1)", border: "1px solid rgba(36, 80, 56, 0.14)", color: "var(--evergreen-800)", fontFamily: "var(--font-mono)", fontSize: "var(--text-lg)", fontWeight: 700, flex: "none" }}>
                  {phaseNum}
                </span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Current court phase</p>
                  <p style={{ margin: "3px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Letters issued {E.appointmentDate}</p>
                </div>
              </div>
              <Badge tone={allDone ? "success" : "brand"}>Phase {phaseNum} of 6</Badge>
            </div>
            <h2 style={{ margin: "18px 0 0", fontFamily: "var(--font-sans)", fontSize: 32, fontWeight: 700, letterSpacing: 0, lineHeight: 1.05, color: "var(--text-strong)" }}>
              {phaseName}
            </h2>
            <p style={{ margin: "8px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
              Next phase: {nextPhaseName}.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "var(--space-4)", marginTop: "var(--space-6)", alignItems: "stretch" }}>
              <div style={{ padding: 14, border: "1px solid rgba(203, 213, 225, 0.66)", borderRadius: 8, background: "rgba(255, 255, 255, 0.72)", boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "var(--radius-full)", background: leadingAlert?.severity === "critical" ? "var(--critical-accent)" : leadingAlert?.severity === "warning" ? "var(--warning-accent)" : "var(--info-accent)", flex: "none" }} />
                  <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Next action</p>
                </div>
                <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", fontWeight: 600, lineHeight: 1.35, color: "var(--text-strong)" }}>
                  {leadingAlert ? leadingAlert.actionRequired : "Monitor upcoming deadlines"}
                </p>
              </div>
              <div style={{ minWidth: 82, padding: 14, border: "1px solid rgba(203, 213, 225, 0.66)", borderRadius: 8, background: "rgba(255, 255, 255, 0.64)", textAlign: "center", boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)" }}>
                <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Open</p>
                <p style={{ margin: "7px 0 0", fontFamily: "var(--font-sans)", fontSize: "var(--text-3xl)", fontWeight: 700, lineHeight: 1, color: open.length ? "var(--critical-text)" : "var(--success-text)", letterSpacing: 0 }}>{open.length}</p>
              </div>
            </div>
          </section>

          <section style={{ padding: "24px 24px 22px", borderBottom: "1px solid rgba(203, 213, 225, 0.62)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 2 }}>
              <div>
                <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Estate ledger</p>
                <h2 style={{ margin: "5px 0 0", fontFamily: "var(--font-sans)", fontSize: "var(--text-xl)", fontWeight: 700, letterSpacing: 0, color: "var(--text-strong)" }}>Recorded position</h2>
              </div>
              <Badge tone={netPosition >= 0 ? "success" : "critical"}>{fmt(netPosition)} net</Badge>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 170px), 1fr))", gap: 10, marginTop: 16 }}>
              <MetricTile label="Assets" value={fmt(assetTotal)} detail={`${E.assets.length} items / ${appraisedCount} appraised`} tone="brand" progress={{ value: appraisedCount, max: E.assets.length, label: `${appraisedCount} of ${E.assets.length} appraisals recorded` }} />
              <MetricTile label="Debts" value={fmt(debtTotal)} detail={`${E.debts.length} creditors / ${notifiedCreditors} notified`} tone="critical" progress={{ value: notifiedCreditors, max: E.debts.length, label: `${notifiedCreditors} of ${E.debts.length} creditor notices logged` }} />
              <MetricTile label="Beneficiaries" value={String(benList.length)} detail={beneficiaryNames} tone="neutral" />
            </div>
          </section>
        </div>

        <div style={{ padding: "18px 24px 22px" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 14, marginBottom: 14 }}>
            <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Probate path</p>
            <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--text-muted)", textAlign: "right" }}>Active: <span style={{ color: "var(--text-strong)", fontWeight: 600 }}>{phaseName}</span></p>
          </div>
          <PhaseRail current={currentIndex} steps={E.phases} />
        </div>
      </Card>

      <section>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--text-strong)" }}>
            What needs your attention
          </h2>
        </div>
        <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
          Open any item for step-by-step instructions. Nothing is dismissed by accident, you mark a step complete when it's truly done.
        </p>
        {justAdvanced ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "var(--space-4)", padding: "var(--space-3) var(--space-4)", background: "var(--success-bg)", border: "1px solid var(--success-border)", borderRadius: "var(--radius-md)", color: "var(--success-text)" }}>
            <I.CheckCircle size={18} color="var(--success-accent)" />
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>Nice work. You've advanced to the {phaseName} phase, here's what's next.</span>
          </div>
        ) : null}
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {open.map((a) => (
            <Alert key={a.id} severity={a.severity} title={a.title} daysRemaining={a.daysRemaining}
              actionRequired={a.actionRequired}
              onOpen={() => onOpenStep && onOpenStep(a.id)} actionLabel="View steps">
              {a.body}
            </Alert>
          ))}
          {open.length === 0 ? (
            <Card tint padded>
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--success-text)" }}>
                <I.CheckCircle size={20} color="var(--success-accent)" />
                <span style={{ fontWeight: 600 }}>You're all caught up. We'll alert you the moment something needs you.</span>
              </div>
            </Card>
          ) : null}
        </div>

        {completed.length ? (
          <div style={{ marginTop: "var(--space-5)" }}>
            <h3 style={{ margin: "0 0 var(--space-3)", fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-subtle)" }}>Completed</h3>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--space-2)" }}>
              {completed.map((a) => (
                <li key={a.id}>
                  <button onClick={() => onOpenStep && onOpenStep(a.id)}
                    style={{ width: "100%", textAlign: "left", display: "flex", alignItems: "center", gap: 10, padding: "11px 16px", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", cursor: "pointer", color: "var(--text-muted)", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)" }}>
                    <I.CheckCircle size={17} color="var(--success-accent)" />
                    <span style={{ textDecoration: "line-through" }}>{a.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "var(--space-6)", alignItems: "start" }}>
        <Card title="Tasks" subtitle="Ordered by what unblocks the estate" padded={false}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {E.tasks.map((t, i) => (
              <li key={t.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "13px 20px", borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)" }}>
                <span style={{ fontSize: "var(--text-sm)", color: t.status === "done" ? "var(--text-muted)" : "var(--text-body)", textDecoration: t.status === "done" ? "line-through" : "none" }}>{t.title}</span>
                <Badge tone={taskTone[t.status]}>{taskLabel[t.status]}</Badge>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Beneficiaries" subtitle="Per the will, open one for full details" padded={false}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {benList.map((b, i) => (
              <li key={b.id}>
                <button onClick={() => setOpenBenId(b.id)}
                  style={{ width: "100%", textAlign: "left", display: "flex", alignItems: "center", gap: 12, padding: "11px 20px", background: "transparent", border: "none", borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)", cursor: "pointer", transition: "background var(--transition-fast)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-sunken)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <Avatar name={b.name} size="sm" />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{b.name}</span>
                    <span style={{ display: "block", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{b.relationship}</span>
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{b.share}</span>
                  <I.ChevronRight size={16} color="var(--text-subtle)" />
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      <BeneficiaryModal
        open={!!openBenId}
        beneficiary={benList.find((b) => b.id === openBenId)}
        onCancel={() => setOpenBenId(null)}
        onSave={(nb) => { setBenList((cur) => cur.map((b) => (b.id === nb.id ? nb : b))); setOpenBenId(null); }}
      />
    </div>
  );
}

// Live dashboard built entirely from the agent's estate state. Shown for real
// (non-demo) estates once at least one document has been parsed.
function RealDashboard({ estate, real }: { estate: EstateProfile; real: EstateState }) {
  const I = ExecutorIcons;
  const fmt = fmtMoney;

  const assetTotal = real.assets.reduce((s, a) => s + (a.estimatedValue ?? a.appraisedValue ?? 0), 0);
  const appraisedCount = real.assets.filter((a) => a.appraised).length;
  const debtTotal = real.debts.reduce((s, d) => s + d.amount, 0);
  const notifiedCreditors = real.debts.filter((d) => d.notified).length;
  const netPosition = assetTotal - debtTotal;

  const phaseNum = Math.min(Math.max(real.phase, 1), PROBATE_PHASES.length);
  const phaseName = PROBATE_PHASES[phaseNum - 1] ?? "In progress";
  const nextPhaseName = PROBATE_PHASES[Math.min(phaseNum, PROBATE_PHASES.length - 1)] ?? phaseName;

  const openAlerts = real.alerts.filter((a) => !a.dismissed);
  const leadingAlert = openAlerts[0];

  const taskTone = { done: "success", todo: "neutral", in_progress: "brand", blocked: "warning" } as const;
  const taskLabel = { done: "Done", todo: "To do", in_progress: "In progress", blocked: "Blocked" } as const;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "36px 40px", display: "grid", gap: "var(--space-8)" }}>
      <header>
        <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Executor dashboard</p>
        <h1 style={{ margin: "8px 0 0", fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>
          The estate of {real.deceasedName}
        </h1>
        <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
          Letters testamentary issued {formatLongDate(real.appointmentDate)}. Built from your documents as you add them.
        </p>
      </header>

      <Card padded={false} style={{ borderRadius: 8 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))" }}>
          <section style={{ padding: "24px 24px 22px", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                <span style={{ width: 42, height: 42, borderRadius: 8, display: "inline-flex", alignItems: "center", justifyContent: "center", background: "rgba(36, 80, 56, 0.1)", border: "1px solid rgba(36, 80, 56, 0.14)", color: "var(--evergreen-800)", fontFamily: "var(--font-mono)", fontSize: "var(--text-lg)", fontWeight: 700, flex: "none" }}>{phaseNum}</span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Current court phase</p>
                  <p style={{ margin: "3px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Letters issued {formatLongDate(real.appointmentDate)}</p>
                </div>
              </div>
              <Badge tone="brand">Phase {phaseNum} of 6</Badge>
            </div>
            <h2 style={{ margin: "18px 0 0", fontFamily: "var(--font-sans)", fontSize: 32, fontWeight: 700, lineHeight: 1.05, color: "var(--text-strong)" }}>{phaseName}</h2>
            <p style={{ margin: "8px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Next phase: {nextPhaseName}.</p>
            <div style={{ marginTop: "var(--space-6)", padding: 14, border: "1px solid var(--border-subtle)", borderRadius: 8, background: "var(--surface-card)" }}>
              <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Next action</p>
              <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", fontWeight: 600, lineHeight: 1.35, color: "var(--text-strong)" }}>{leadingAlert ? leadingAlert.actionRequired : "Add more documents and I'll surface the next deadline."}</p>
            </div>
          </section>

          <section style={{ padding: "24px 24px 22px", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div>
                <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Estate ledger</p>
                <h2 style={{ margin: "5px 0 0", fontFamily: "var(--font-sans)", fontSize: "var(--text-xl)", fontWeight: 700, color: "var(--text-strong)" }}>Recorded position</h2>
              </div>
              <Badge tone={netPosition >= 0 ? "success" : "critical"}>{fmt(netPosition)} net</Badge>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 170px), 1fr))", gap: 10, marginTop: 16 }}>
              <MetricTile label="Assets" value={fmt(assetTotal)} detail={`${real.assets.length} items / ${appraisedCount} appraised`} tone="brand" progress={{ value: appraisedCount, max: Math.max(real.assets.length, 1), label: `${appraisedCount} of ${real.assets.length} appraisals recorded` }} />
              <MetricTile label="Debts" value={fmt(debtTotal)} detail={`${real.debts.length} creditors / ${notifiedCreditors} notified`} tone="critical" progress={{ value: notifiedCreditors, max: Math.max(real.debts.length, 1), label: `${notifiedCreditors} of ${real.debts.length} creditor notices logged` }} />
              <MetricTile label="Beneficiaries" value={String(real.beneficiaries.length)} detail={real.beneficiaries.map((b) => b.name.split(" ")[0]).join(", ") || "None yet"} tone="neutral" />
            </div>
          </section>
        </div>
        <div style={{ padding: "18px 24px 22px" }}>
          <p style={{ margin: "0 0 14px", fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Probate path</p>
          <PhaseRail current={phaseNum - 1} steps={PROBATE_PHASES} />
        </div>
      </Card>

      <section>
        <h2 style={{ margin: "0 0 var(--space-2)", fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--text-strong)" }}>What needs your attention</h2>
        <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Surfaced by the DeadlineAgent from your estate and California probate rules.</p>
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {openAlerts.map((a) => (
            <Alert key={a.id} severity={a.severity} title={a.title} daysRemaining={a.daysRemaining ?? undefined}
              actionRequired={a.actionRequired}>
              {a.body}
            </Alert>
          ))}
          {openAlerts.length === 0 ? (
            <Card tint padded>
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--success-text)" }}>
                <I.CheckCircle size={20} color="var(--success-accent)" />
                <span style={{ fontWeight: 600 }}>Nothing needs you right now. I'll alert you the moment something does.</span>
              </div>
            </Card>
          ) : null}
        </div>
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "var(--space-6)", alignItems: "start" }}>
        <Card title="Tasks" subtitle="Ordered by what unblocks the estate" padded={false}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {real.tasks.length === 0 ? (
              <li style={{ padding: "18px 20px", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>No tasks yet. They appear as documents are parsed.</li>
            ) : real.tasks.map((t, i) => (
              <li key={t.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "13px 20px", borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)" }}>
                <span style={{ fontSize: "var(--text-sm)", color: t.status === "done" ? "var(--text-muted)" : "var(--text-body)", textDecoration: t.status === "done" ? "line-through" : "none" }}>{t.title}</span>
                <Badge tone={taskTone[t.status]}>{taskLabel[t.status]}</Badge>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Beneficiaries" subtitle="Per the will" padded={false}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {real.beneficiaries.length === 0 ? (
              <li style={{ padding: "18px 20px", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>None identified yet.</li>
            ) : real.beneficiaries.map((b, i) => (
              <li key={b.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 20px", borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)" }}>
                <Avatar name={b.name} size="sm" />
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{b.name}</span>
                </span>
                {b.share ? <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{b.share}</span> : null}
              </li>
            ))}
          </ul>
        </Card>
      </section>
    </div>
  );
}
