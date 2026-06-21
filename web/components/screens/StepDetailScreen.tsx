"use client";
// Full-page instructions for a single attention item, with a confirmed completion.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Badge, Button, Dialog } from "@/components/ds";
import { formatAlertTimingLabel } from "@/lib/alertTiming";
import type { Alert } from "@/lib/design/data";

type Props = {
  item: Alert | null;
  completed: boolean;
  completing?: boolean;
  error?: string | null;
  onBack: () => void;
  onComplete: (id: string) => Promise<void> | void;
};

export function StepDetailScreen({ item, completed, completing = false, error = null, onBack, onComplete }: Props) {
  const I = ExecutorIcons;
  const [confirm, setConfirm] = React.useState(false);

  if (!item) return null;

  const sectionTitle = (text: string) => (
    <h2 style={{ margin: "0 0 var(--space-3)", fontFamily: "var(--font-display)", fontSize: "var(--text-lg)", fontWeight: 600, color: "var(--text-strong)" }}>{text}</h2>
  );

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "28px 40px 48px" }}>
      <button onClick={onBack}
        style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "none", background: "transparent", cursor: "pointer", color: "var(--text-muted)", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 500, padding: "4px 0", marginBottom: "var(--space-5)" }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
        Back to dashboard
      </button>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "var(--space-3)" }}>
        <Badge tone={item.severity} dot>{item.severity}</Badge>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-muted)" }}>
          {formatAlertTimingLabel(item)}
        </span>
      </div>

      <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: 1.15, color: "var(--text-strong)" }}>
        {item.title}
      </h1>

      {completed ? (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: "var(--space-5)", padding: "var(--space-4) var(--space-5)", background: "var(--success-bg)", border: "1px solid var(--success-border)", borderRadius: "var(--radius-md)", color: "var(--success-text)" }}>
          <I.CheckCircle size={20} color="var(--success-accent)" />
          <span style={{ fontWeight: 600 }}>You marked this step complete. Nice work.</span>
        </div>
      ) : null}

      <section style={{ marginTop: "var(--space-8)" }}>
        {sectionTitle("Why this matters")}
        <p style={{ margin: 0, fontSize: "var(--text-md)", lineHeight: "var(--leading-relaxed)", color: "var(--text-body)" }}>{item.body}</p>
        {item.rule ? (
          <p style={{ margin: "var(--space-3) 0 0", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{item.rule}</p>
        ) : null}
      </section>

      {item.whatYouNeed && item.whatYouNeed.length ? (
        <section style={{ marginTop: "var(--space-8)" }}>
          {sectionTitle("What you'll need")}
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--space-2)" }}>
            {item.whatYouNeed.map((w, i) => (
              <li key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: "var(--text-base)", color: "var(--text-body)" }}>
                <span style={{ marginTop: 3, color: "var(--text-subtle)", flex: "none" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="m9 12 2 2 4-4" /></svg>
                </span>
                {w}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section style={{ marginTop: "var(--space-8)" }}>
        {sectionTitle("How to do it")}
        <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--space-4)" }}>
          {item.steps && item.steps.map((s, i) => (
            <li key={i} style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
              <span style={{ flex: "none", width: 28, height: 28, borderRadius: "999px", background: "var(--evergreen-100)", color: "var(--evergreen-800)", display: "inline-flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600 }}>{i + 1}</span>
              <p style={{ margin: 0, paddingTop: 3, fontSize: "var(--text-base)", lineHeight: "var(--leading-relaxed)", color: "var(--text-body)" }}>{s}</p>
            </li>
          ))}
        </ol>
      </section>

      {error ? (
        <div style={{ marginTop: "var(--space-6)", padding: "var(--space-4) var(--space-5)", background: "var(--critical-bg)", border: "1px solid var(--critical-border)", borderRadius: "var(--radius-md)", color: "var(--critical-text)", fontSize: "var(--text-sm)", fontWeight: 500 }}>
          {error}
        </div>
      ) : null}

      <div style={{ marginTop: "var(--space-10)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-4)", paddingTop: "var(--space-6)", borderTop: "1px solid var(--border-subtle)" }}>
        <Button variant="secondary" onClick={onBack}>Back</Button>
        {completed ? (
          <Badge tone="success" dot>Completed</Badge>
        ) : (
          <Button variant="primary" leadingIcon={<I.Check size={16} />} onClick={() => setConfirm(true)} disabled={completing}>
            {completing ? "Marking complete..." : "Mark this step complete"}
          </Button>
        )}
      </div>

      <Dialog
        open={confirm}
        title="Mark this step complete?"
        confirmLabel="Yes, mark complete"
        cancelLabel="Not yet"
        onConfirm={() => { setConfirm(false); void onComplete(item.id); }}
        onCancel={() => { if (!completing) setConfirm(false); }}
      >
        We'll move "{item.title}" off your attention list and into completed steps. You can reopen it any time, nothing is deleted.
      </Dialog>
    </div>
  );
}
