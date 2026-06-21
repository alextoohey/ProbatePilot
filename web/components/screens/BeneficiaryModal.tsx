"use client";
// Beneficiary profile, more detail per the will (not an Executor AI account).
import React from "react";
import { Input, Select, Button, Avatar } from "@/components/ds";
import type { Beneficiary } from "@/lib/design/data";

type Props = {
  open: boolean;
  beneficiary?: Beneficiary;
  onCancel: () => void;
  onSave: (b: Beneficiary) => void;
};

export function BeneficiaryModal({ open, beneficiary, onCancel, onSave }: Props) {
  const [f, setF] = React.useState<Beneficiary>(beneficiary || ({} as Beneficiary));
  const set =
    (k: keyof Beneficiary) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setF((c) => ({ ...c, [k]: e.target.value }));

  React.useEffect(() => {
    if (open && beneficiary) setF(beneficiary);
  }, [open, beneficiary]);
  if (!open || !beneficiary) return null;

  return (
    <div
      role="presentation"
      onClick={onCancel}
      style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(17,24,28,0.42)", backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-6)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Beneficiary details"
        onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 540, maxHeight: "90vh", overflowY: "auto", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-lg)", fontFamily: "var(--font-sans)" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "var(--space-5) var(--space-5) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
          <Avatar name={f.name || "?"} size="lg" />
          <div>
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>{f.name}</h2>
            <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Beneficiary details from the will. Edit anything that needs correcting.</p>
          </div>
        </div>

        <div style={{ padding: "var(--space-5)", display: "grid", gap: "var(--space-4)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Select
              label="Relationship to the deceased"
              value={f.relationship}
              onChange={set("relationship")}
              options={["Spouse", "Daughter", "Son", "Child", "Parent", "Sibling", "Grandchild", "Other family", "Friend", "Charity", "Other"]}
            />
            <Input label="Share of the estate" value={f.share} onChange={set("share")} />
          </div>
          <Input label="Specific bequest" value={f.specificBequest} onChange={set("specificBequest")} hint="Anything left to them by name in the will." />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Input label="Email" type="email" value={f.email} onChange={set("email")} />
            <Input label="Phone" value={f.phone} onChange={set("phone")} />
          </div>
          <Input label="Mailing address" value={f.address} onChange={set("address")} />
          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-strong)", marginBottom: 6 }}>Notes</label>
            <textarea
              value={f.notes || ""}
              onChange={set("notes")}
              rows={2}
              placeholder="Anything to remember for distribution"
              style={{ width: "100%", boxSizing: "border-box", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)", lineHeight: "var(--leading-normal)", color: "var(--text-body)", background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "10px 12px", outline: "none", resize: "vertical" }}
            />
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)" }}>
          <Button variant="secondary" onClick={onCancel}>Close</Button>
          <Button variant="primary" onClick={() => onSave(f)}>Save changes</Button>
        </div>
      </div>
    </div>
  );
}
