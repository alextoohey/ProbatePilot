"use client";

import React from "react";
import { Input, Select, Button, Avatar } from "@/components/ds";
import { GENDER_OPTIONS, US_STATES, ExecutorProfile } from "@/lib/design/data";

const O = { GENDER_OPTIONS, US_STATES };

type Props = {
  open: boolean;
  profile: ExecutorProfile;
  onCancel: () => void;
  onSave: (profile: ExecutorProfile) => void;
};

// Modal form to edit the signed-in executor's account / profile.
export function ProfileEditorModal({ open, profile, onCancel, onSave }: Props) {
  const [f, setF] = React.useState(profile);
  const set =
    (k: keyof ExecutorProfile) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setF((c) => ({ ...c, [k]: e.target.value }));

  React.useEffect(() => { if (open) setF(profile); }, [open, profile]);
  if (!open) return null;

  return (
    <div role="presentation" onClick={onCancel}
      style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(17,24,28,0.42)", backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-6)" }}>
      <div role="dialog" aria-modal="true" aria-label="Your profile" onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 560, maxHeight: "90vh", overflowY: "auto", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-lg)", fontFamily: "var(--font-sans)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "var(--space-5) var(--space-5) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
          <Avatar name={f.name || "?"} size="lg" />
          <div>
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>Your profile</h2>
            <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Details we use to tailor probate guidance and pre-fill your letters.</p>
          </div>
        </div>

        <div style={{ padding: "var(--space-5)", display: "grid", gap: "var(--space-4)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Input label="Full name" value={f.name} onChange={set("name")} />
            <Input label="Email" type="email" value={f.email} onChange={set("email")} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Input label="Phone" value={f.phone} onChange={set("phone")} />
            <Select label="Relationship to the deceased" value={f.relationship} onChange={set("relationship")} options={["Daughter of the deceased","Son of the deceased","Spouse of the deceased","Sibling of the deceased","Other family","Friend","Attorney"]} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Input label="Age" type="number" value={f.age} onChange={set("age")} />
            <Select label="Gender" value={f.gender} onChange={set("gender")} options={O.GENDER_OPTIONS} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
            <Select label="State" value={f.state} onChange={set("state")} options={O.US_STATES} />
            <Input label="County" value={f.county} onChange={set("county")} />
          </div>
          <Input label="Mailing address" value={f.address} onChange={set("address")} />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)", position: "sticky", bottom: 0 }}>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--text-subtle)" }}>Signed in as {profile.email}</span>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button variant="secondary" onClick={onCancel}>Cancel</Button>
            <Button variant="primary" onClick={() => onSave(f)}>Save changes</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
