"use client";
// Dashboard, estate overview, the DeadlineAgent's ranked alerts, and tasks.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Card, StatBlock, Alert, Badge, ProgressSteps, Button, Avatar } from "@/components/ds";
import { DEMO_ESTATE, fmtMoney, type EstateProfile, type Beneficiary } from "@/lib/design/data";
import { BeneficiaryModal } from "./BeneficiaryModal";

type Props = {
  estate?: EstateProfile;
  completedIds?: string[];
  onOpenStep?: (id: string) => void;
  onGoDocuments?: () => void;
};

export function DashboardScreen({ estate, completedIds = [], onOpenStep, onGoDocuments }: Props) {
  const E = DEMO_ESTATE;
  const fmt = fmtMoney;
  const I = ExecutorIcons;
  const [benList, setBenList] = React.useState<Beneficiary[]>(E.beneficiaries.map((b) => ({ ...b })));
  const [openBenId, setOpenBenId] = React.useState<string | null>(null);

  // A newly created estate has no documents yet, show onboarding.
  if (estate && !estate.seeded) {
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

      <Card padded={true}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-6)", marginBottom: "var(--space-6)" }}>
          <StatBlock label="Assets" value={fmt(assetTotal)} sub={`${E.assets.length} items, 2 appraised`} />
          <StatBlock label="Debts" value={fmt(debtTotal)} tone="critical" sub={`${E.debts.length} creditors`} />
          <StatBlock label="Beneficiaries" value={String(E.beneficiaries.length)} sub="Dana, Sarah, Marcus" />
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
