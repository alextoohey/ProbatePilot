"use client";
// Dashboard, estate overview, the DeadlineAgent's ranked alerts, and tasks.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Card, StatBlock, Alert, Badge, ProgressSteps, Button, Avatar } from "@/components/ds";
import { DEMO_ESTATE, fmtMoney, type EstateProfile, type Beneficiary, type Alert as DesignAlert } from "@/lib/design/data";
import { getEstate } from "@/lib/agentClient";
import { BeneficiaryModal } from "./BeneficiaryModal";
import type { Alert as BackendAlert, EstateState } from "@/types";

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
  liveAlerts?: BackendAlert[] | null;
  liveEstate?: EstateState | null;
  liveAlertsFailed?: boolean;
};

export function DashboardScreen({ estate, completedIds = [], onOpenStep, onGoDocuments, liveAlerts = null, liveEstate, liveAlertsFailed = false }: Props) {
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

  // A newly created estate has no documents yet, show onboarding; once any
  // document is parsed, show the live estate built from real data.
  if (isReal && estate) {
    if (loadingReal) {
      return (
        <div style={{ display: "flex", height: "100%", minHeight: 320, alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)" }}>
          Loading the estate…
        </div>
      );
    }
    if (real && real.documents.length > 0) {
      return <RealDashboard real={real} />;
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

  const guidanceAlerts = [...E.alerts, ...(E.alertsNext || [])];
  const liveAlertsLoading = estate?.seeded && liveAlerts === null;
  const allAlerts: DesignAlert[] = liveAlerts === null
    ? []
    : liveAlerts.length > 0
      ? liveAlerts.map((a) => {
        const guidance = guidanceAlerts.find((g) => g.id === a.id);
        return {
          ...a,
          steps: guidance?.steps || [],
          whatYouNeed: guidance?.whatYouNeed || [],
          daysRemaining: a.daysRemaining ?? undefined,
        };
      })
      : estate?.seeded
        ? []
        : guidanceAlerts;
  const open = allAlerts.filter((a) => !done.has(a.id) && !(a as BackendAlert).dismissed);
  const completed = allAlerts.filter((a) => done.has(a.id) || !!(a as BackendAlert).dismissed);
  const justAdvanced = false;

  const assetTotal = liveEstate
    ? liveEstate.assets.reduce((s, a) => s + (a.estimatedValue ?? 0), 0)
    : E.assets.reduce((s, a) => s + a.value, 0);
  const debtTotal = liveEstate
    ? liveEstate.debts.reduce((s, d) => s + d.amount, 0)
    : E.debts.reduce((s, d) => s + d.amount, 0);

  const taskTone = { done: "success", todo: "neutral", blocked: "warning" } as const;
  const taskLabel = { done: "Done", todo: "To do", blocked: "Blocked" } as const;

  const allDone = open.length === 0;
  const currentPhase = liveEstate ? liveEstate.phase : E.phase;
  const currentIndex = Math.min(currentPhase - 1, E.phases.length - 1);
  const phaseNum = currentIndex + 1;
  const phaseName = E.phases[currentIndex];
  const deceasedName = liveEstate ? liveEstate.deceasedName : E.deceasedName;
  const appointmentDate = liveEstate ? liveEstate.appointmentDate : E.appointmentDate;
  const beneficiaryCount = liveEstate ? liveEstate.beneficiaries.length : E.beneficiaries.length;
  const assetCount = liveEstate ? liveEstate.assets.length : E.assets.length;
  const appraisedCount = liveEstate
    ? liveEstate.assets.filter((a) => a.appraised).length
    : E.assets.filter((a) => a.appraised).length;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "36px 40px", display: "grid", gap: "var(--space-8)" }}>
      <header>
        <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>Executor dashboard</p>
        <h1 style={{ margin: "8px 0 0", fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>
          The estate of {deceasedName}
        </h1>
        <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
          Letters testamentary issued {appointmentDate}. Here's where things stand, and the next thing to handle.
        </p>
      </header>

      <Card padded={true}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-6)", marginBottom: "var(--space-6)" }}>
          <StatBlock label="Assets" value={fmt(assetTotal)} sub={`${assetCount} items, ${appraisedCount} appraised`} />
          <StatBlock label="Debts" value={fmt(debtTotal)} tone="critical" sub={`${liveEstate ? liveEstate.debts.length : E.debts.length} creditors`} />
          <StatBlock label="Beneficiaries" value={String(beneficiaryCount)} sub={liveEstate ? liveEstate.beneficiaries.map((b) => b.name.split(" ")[0]).join(", ") : "Dana, Sarah, Marcus"} />
          <StatBlock label="Phase" value={`${phaseNum} of 6`} tone={allDone ? "success" : "brand"} sub={phaseName} />
        </div>
        <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "var(--space-6)" }}>
          <ProgressSteps current={currentIndex} steps={E.phases} />
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
          {liveAlertsLoading ? (
            <Card tint padded>
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--text-muted)" }}>
                <I.Bell size={18} color="var(--text-subtle)" />
                <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>Checking California probate deadlines...</span>
              </div>
            </Card>
          ) : null}
          {liveAlertsFailed ? (
            <Card tint padded>
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--warning-text)" }}>
                <I.Bell size={18} color="var(--warning-accent)" />
                <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>DeadlineAgent alerts could not be loaded. Start the Python agent and refresh.</span>
              </div>
            </Card>
          ) : null}
          {!liveAlertsLoading && !liveAlertsFailed && open.map((a) => (
            <Alert key={a.id} severity={a.severity} title={a.title} daysRemaining={a.daysRemaining ?? undefined}
              actionRequired={a.actionRequired}
              onOpen={() => onOpenStep && onOpenStep(a.id)} actionLabel="View steps">
              {a.body}
            </Alert>
          ))}
          {!liveAlertsLoading && !liveAlertsFailed && open.length === 0 ? (
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
// (non-demo) estates once at least one document has been parsed. Unlike the demo
// view it never falls back to seed data, so it only ever shows this estate.
function RealDashboard({ real }: { real: EstateState }) {
  const I = ExecutorIcons;
  const fmt = fmtMoney;
  const phases = DEMO_ESTATE.phases;

  const assetTotal = real.assets.reduce((s, a) => s + (a.estimatedValue ?? a.appraisedValue ?? 0), 0);
  const appraisedCount = real.assets.filter((a) => a.appraised).length;
  const debtTotal = real.debts.reduce((s, d) => s + d.amount, 0);
  const notifiedCreditors = real.debts.filter((d) => d.notified).length;
  const netPosition = assetTotal - debtTotal;

  const phaseNum = Math.min(Math.max(real.phase, 1), phases.length);
  const phaseName = phases[phaseNum - 1] ?? "In progress";
  const openAlerts = real.alerts.filter((a) => !a.dismissed);

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

      <Card padded={true}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-6)", marginBottom: "var(--space-6)" }}>
          <StatBlock label="Assets" value={fmt(assetTotal)} sub={`${real.assets.length} items, ${appraisedCount} appraised`} />
          <StatBlock label="Debts" value={fmt(debtTotal)} tone="critical" sub={`${real.debts.length} creditors, ${notifiedCreditors} notified`} />
          <StatBlock label="Beneficiaries" value={String(real.beneficiaries.length)} sub={real.beneficiaries.map((b) => b.name.split(" ")[0]).join(", ") || "None yet"} />
          <StatBlock label="Phase" value={`${phaseNum} of 6`} tone="brand" sub={phaseName} />
        </div>
        <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "var(--space-6)" }}>
          <ProgressSteps current={phaseNum - 1} steps={phases} />
        </div>
      </Card>

      <section>
        <h2 style={{ margin: "0 0 var(--space-2)", fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--text-strong)" }}>What needs your attention</h2>
        <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Surfaced by the DeadlineAgent from your estate and California probate rules.</p>
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {openAlerts.map((a) => (
            <Alert key={a.id} severity={a.severity} title={a.title} daysRemaining={a.daysRemaining ?? undefined} actionRequired={a.actionRequired}>
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
