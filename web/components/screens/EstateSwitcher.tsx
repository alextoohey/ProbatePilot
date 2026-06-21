"use client";
// Slack-style estate switcher at the top of the sidebar.
import React from "react";
import { Avatar } from "@/components/ds";
import { ExecutorIcons } from "@/lib/design/icons";
import type { EstateProfile } from "@/lib/design/data";

const I = ExecutorIcons;

type Props = {
  estates: EstateProfile[];
  activeId: string;
  onSwitch: (id: string) => void;
  onCreate: () => void;
};

export function EstateSwitcher({ estates, activeId, onSwitch, onCreate }: Props) {
  const [open, setOpen] = React.useState(false);
  const active = estates.find((e) => e.id === activeId) || estates[0];

  return (
    <div style={{ position: "relative", padding: "0 12px 8px" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left",
          padding: "8px 10px", borderRadius: "var(--radius-md)", cursor: "pointer",
          background: open ? "var(--surface-sunken)" : "transparent",
          border: "1px solid " + (open ? "var(--border-default)" : "transparent"),
          transition: "background var(--transition-fast)",
        }}
      >
        <Avatar name={active.deceasedName} size="sm" />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{active.deceasedName}</span>
        </span>
        <span style={{ color: "var(--text-subtle)", display: "inline-flex" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="m7 15 5 5 5-5" /><path d="m7 9 5-5 5 5" /></svg>
        </span>
      </button>

      {open ? (
        <React.Fragment>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
          <div style={{
            position: "absolute", top: "100%", left: 12, right: 12, zIndex: 50, marginTop: 4,
            background: "var(--surface-card)", border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", overflow: "hidden", padding: 6,
          }}>
            <div style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-subtle)", padding: "6px 8px 4px" }}>Estates</div>
            {estates.map((e) => {
              const on = e.id === activeId;
              return (
                <button key={e.id} onClick={() => { onSwitch(e.id); setOpen(false); }}
                  style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", padding: "8px", borderRadius: "var(--radius-sm)", border: "none", cursor: "pointer", background: on ? "var(--evergreen-50)" : "transparent" }}>
                  <Avatar name={e.deceasedName} size="sm" tone={on ? "brand" : "neutral"} />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{e.deceasedName}</span>
                    {!e.seeded ? <span style={{ display: "block", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Setup in progress</span> : null}
                  </span>
                  {on ? <I.Check size={16} color="var(--evergreen-700)" /> : null}
                </button>
              );
            })}
            <div style={{ height: 1, background: "var(--border-subtle)", margin: "6px 4px" }} />
            <button onClick={() => { onCreate(); setOpen(false); }}
              style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", padding: "8px", borderRadius: "var(--radius-sm)", border: "none", cursor: "pointer", background: "transparent", color: "var(--text-brand)", fontWeight: 600 }}>
              <span style={{ width: 28, height: 28, borderRadius: "999px", background: "var(--evergreen-100)", display: "inline-flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                <I.Plus size={16} color="var(--evergreen-700)" />
              </span>
              <span style={{ fontSize: "var(--text-sm)" }}>Create new estate</span>
            </button>
          </div>
        </React.Fragment>
      ) : null}
    </div>
  );
}
