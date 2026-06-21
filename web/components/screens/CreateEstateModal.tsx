"use client";

import React from "react";
import { Input, Select, Button } from "@/components/ds";
import { ROLE_OPTIONS, RELATIONSHIP_OPTIONS, US_STATES } from "@/lib/design/data";
import type { EstateProfile } from "@/lib/design/data";

// Modal form to add a new estate the executor will administer.
type Props = {
  open: boolean;
  onCancel: () => void;
  onCreate: (estate: EstateProfile) => void;
};

export function CreateEstateModal({ open, onCancel, onCreate }: Props) {
  const [f, setF] = React.useState({ deceasedName: "", dateOfDeath: "", relationship: "Parent", role: "Executor", state: "California", county: "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((c) => ({ ...c, [k]: e.target.value }));

  React.useEffect(() => { if (open) setF({ deceasedName: "", dateOfDeath: "", relationship: "Parent", role: "Executor", state: "California", county: "" }); }, [open]);
  if (!open) return null;

  const valid = f.deceasedName.trim().length > 1;
  function submit() {
    if (!valid) return;
    onCreate({
      id: "est-" + Date.now(),
      deceasedName: f.deceasedName.trim(),
      role: f.role, relationship: f.relationship,
      state: f.state, county: f.county.trim() || "Not set",
      phase: 1, seeded: false, hasDocuments: false,
    });
  }

  return (
    <div role="presentation" onClick={onCancel}
      style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(17,24,28,0.42)", backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-6)" }}>
      <div role="dialog" aria-modal="true" aria-label="Add an estate" onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 520, background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-lg)", fontFamily: "var(--font-sans)", overflow: "hidden" }}>
        <div style={{ padding: "var(--space-5) var(--space-5) var(--space-3)" }}>
          <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>Add an estate</h2>
          <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Start a new estate you're responsible for. You can add documents next.</p>
        </div>
        <div style={{ padding: "0 var(--space-5) var(--space-5)", display: "grid", gap: "var(--space-4)" }}>
          <Input label="Deceased's full name" value={f.deceasedName} onChange={set("deceasedName")} placeholder="e.g. Gloria Reyes" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Input label="Date of death" type="date" value={f.dateOfDeath} onChange={set("dateOfDeath")} />
            <Select label="Your relationship" value={f.relationship} onChange={set("relationship")} options={RELATIONSHIP_OPTIONS} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-4)" }}>
            <Select label="Your role" value={f.role} onChange={set("role")} options={ROLE_OPTIONS} />
            <Select label="State" value={f.state} onChange={set("state")} options={US_STATES} />
            <Input label="County" value={f.county} onChange={set("county")} placeholder="e.g. Alameda" />
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)" }}>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant="primary" disabled={!valid} onClick={submit}>Create estate</Button>
        </div>
      </div>
    </div>
  );
}
