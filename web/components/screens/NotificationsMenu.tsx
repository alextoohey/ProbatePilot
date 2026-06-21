"use client";

import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { EXECUTOR_PROFILE } from "@/lib/design/data";

const I = ExecutorIcons;

type Prefs = { all: boolean; deadlines: boolean; weekly: boolean; email: boolean };

type Props = {
  prefs: Prefs;
  setPrefs: (updater: (p: Prefs) => Prefs) => void;
};

// Bell button + notifications settings popover (top-right of the app).
export function NotificationsMenu({ prefs, setPrefs }: Props) {
  const [open, setOpen] = React.useState(false);
  const on = prefs.all;

  function Switch({
    checked,
    onChange,
    disabled,
  }: {
    checked: boolean;
    onChange: (v: boolean) => void;
    disabled?: boolean;
  }) {
    return (
      <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
        style={{
          width: 38, height: 22, flex: "none", borderRadius: "999px", border: "none", padding: 2, cursor: disabled ? "not-allowed" : "pointer",
          background: checked ? "var(--evergreen-700)" : "var(--ink-300)", opacity: disabled ? 0.45 : 1,
          transition: "background var(--transition-fast)", display: "inline-flex", justifyContent: checked ? "flex-end" : "flex-start",
        }}>
        <span style={{ width: 18, height: 18, borderRadius: "999px", background: "#fff", boxShadow: "var(--shadow-xs)", transition: "all var(--transition-fast)" }} />
      </button>
    );
  }

  const row = (key: keyof Prefs, label: string, desc: string, disabled: boolean) => (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "10px 0" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: disabled ? "var(--text-subtle)" : "var(--text-strong)" }}>{label}</div>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.4 }}>{desc}</div>
      </div>
      <Switch checked={!!prefs[key] && (key === "all" || on)} disabled={disabled} onChange={(v) => setPrefs((p) => ({ ...p, [key]: v }))} />
    </div>
  );

  return (
    <div style={{ position: "relative" }}>
      <button onClick={() => setOpen((o) => !o)} aria-label="Notification settings" title="Notifications"
        style={{ position: "relative", width: 36, height: 36, borderRadius: "var(--radius-md)", border: "1px solid " + (open ? "var(--border-default)" : "transparent"), background: open ? "var(--surface-sunken)" : "transparent", cursor: "pointer", color: "var(--text-muted)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
        <I.Bell size={18} />
        {!on ? (
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-subtle)" strokeWidth="1.75" strokeLinecap="round" style={{ position: "absolute", inset: 0, margin: "auto" }}><path d="m4 4 16 16" /></svg>
        ) : (
          <span style={{ position: "absolute", top: 7, right: 8, width: 7, height: 7, borderRadius: "999px", background: "var(--warning-accent)", border: "1.5px solid var(--paper-50)" }} />
        )}
      </button>

      {open ? (
        <React.Fragment>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
          <div style={{ position: "absolute", top: "100%", right: 0, marginTop: 6, zIndex: 50, width: 300, background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", padding: "var(--space-4) var(--space-5)", fontFamily: "var(--font-sans)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, paddingBottom: 6 }}>
              <div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: "var(--text-md)", fontWeight: 600, color: "var(--text-strong)" }}>Notifications</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{on ? "You'll be alerted before deadlines" : "All notifications are paused"}</div>
              </div>
              <Switch checked={on} onChange={(v) => setPrefs((p) => ({ ...p, all: v }))} />
            </div>
            <div style={{ height: 1, background: "var(--border-subtle)", margin: "4px 0" }} />
            {row("deadlines", "Deadline & liability alerts", "The DeadlineAgent warns you before a window closes.", !on)}
            {row("weekly", "Weekly summary", "A Monday digest of what's open and what's done.", !on)}
            {row("email", "Email me copies", "Send the same alerts to " + (EXECUTOR_PROFILE ? EXECUTOR_PROFILE.email : "your inbox") + ".", !on)}
          </div>
        </React.Fragment>
      ) : null}
    </div>
  );
}
