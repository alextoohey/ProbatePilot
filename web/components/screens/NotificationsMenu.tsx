"use client";

import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { sendAlertEmail } from "@/lib/agentClient";
import type { Alert } from "@/types";

const I = ExecutorIcons;

export type NotifPrefs = { all: boolean; deadlines: boolean; weekly: boolean; email: boolean };

type EmailPreview = { subject: string; body: string; sent: boolean; reason: string; recipient?: string | null };

type Props = {
  prefs: NotifPrefs;
  setPrefs: (updater: (p: NotifPrefs) => NotifPrefs) => void;
  alerts?: Alert[];
  estateId: string;
  executorEmail?: string;
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "var(--critical-accent, #d64545)",
  warning: "var(--warning-accent)",
  info: "var(--evergreen-500)",
};

function readKey(estateId: string) {
  return `ec:notifRead:${estateId}`;
}

function loadReadIds(estateId: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(readKey(estateId));
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function saveReadIds(estateId: string, ids: Set<string>) {
  try {
    window.localStorage.setItem(readKey(estateId), JSON.stringify(Array.from(ids)));
  } catch {
    /* ignore storage failures (private mode, quota) */
  }
}

// Bell button + notifications panel (top-right of the app): a live feed of the
// DeadlineAgent alerts, plus the settings that control them.
export function NotificationsMenu({ prefs, setPrefs, alerts = [], estateId, executorEmail }: Props) {
  const [open, setOpen] = React.useState(false);
  const [showSettings, setShowSettings] = React.useState(false);
  const [readIds, setReadIds] = React.useState<Set<string>>(() => loadReadIds(estateId));
  const [sending, setSending] = React.useState<null | "alerts" | "weekly">(null);
  const [emailMsg, setEmailMsg] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<EmailPreview | null>(null);
  const on = prefs.all;

  // Reload read-state when switching estates.
  React.useEffect(() => { setReadIds(loadReadIds(estateId)); setEmailMsg(null); setPreview(null); }, [estateId]);

  // Respect the toggles: paused → nothing; deadlines off → drop deadline/liability.
  const visible = React.useMemo(() => {
    if (!on) return [];
    return alerts
      .filter((a) => !a.dismissed)
      .filter((a) => (prefs.deadlines ? true : a.type !== "deadline" && a.type !== "liability"));
  }, [alerts, on, prefs.deadlines]);

  const unread = visible.filter((a) => !readIds.has(a.id)).length;

  function markRead(ids: string[]) {
    setReadIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.add(id));
      saveReadIds(estateId, next);
      return next;
    });
  }

  function openPanel() {
    setOpen((o) => !o);
  }

  async function sendEmail(kind: "alerts" | "weekly") {
    if (sending) return;
    setSending(kind);
    setEmailMsg(null);
    try {
      const res = await sendAlertEmail(estateId, executorEmail, kind);
      // Always open the preview so the composed email is visible — whether it
      // was actually delivered or sending just isn't configured yet.
      setPreview({ subject: res.subject, body: res.body, sent: res.sent, reason: res.reason, recipient: res.recipient });
    } catch {
      setEmailMsg("Couldn't reach the email service. Make sure the agent is running.");
    } finally {
      setSending(null);
    }
  }

  function previewStatus(p: EmailPreview): string {
    if (p.sent) return `Sent to ${p.recipient ?? "your inbox"}.`;
    if (p.reason === "email_not_configured") return `Sample preview for ${p.recipient ?? "the executor"} — sending isn't set up yet (add RESEND_API_KEY + EMAIL_FROM to deliver it).`;
    if (p.reason === "missing_recipient") return "Preview — no email is on file for the executor.";
    if (p.reason.startsWith("provider_error")) return `Preview for ${p.recipient ?? "the executor"} — the email provider rejected it. In Resend's test mode you can only email your own account address; verify a domain to email anyone.`;
    return "Preview — the message couldn't be sent.";
  }

  function Switch({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
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

  const row = (key: keyof NotifPrefs, label: string, desc: string, disabled: boolean) => (
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
      <button onClick={openPanel} aria-label="Notifications" title="Notifications"
        style={{ position: "relative", width: 36, height: 36, borderRadius: "var(--radius-md)", border: "1px solid " + (open ? "var(--border-default)" : "transparent"), background: open ? "var(--surface-sunken)" : "transparent", cursor: "pointer", color: "var(--text-muted)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
        <I.Bell size={18} />
        {!on ? (
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-subtle)" strokeWidth="1.75" strokeLinecap="round" style={{ position: "absolute", inset: 0, margin: "auto" }}><path d="m4 4 16 16" /></svg>
        ) : unread > 0 ? (
          <span style={{ position: "absolute", top: 2, right: 1, minWidth: 16, height: 16, padding: "0 4px", borderRadius: "999px", background: "var(--critical-accent, #d64545)", color: "#fff", fontSize: 10, fontWeight: 700, lineHeight: "16px", textAlign: "center", border: "1.5px solid var(--paper-50)", boxSizing: "content-box" }}>{unread > 9 ? "9+" : unread}</span>
        ) : null}
      </button>

      {open ? (
        <React.Fragment>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
          <div style={{ position: "absolute", top: "100%", right: 0, marginTop: 6, zIndex: 50, width: 340, maxWidth: "calc(100vw - 32px)", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", fontFamily: "var(--font-sans)", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "var(--space-4) var(--space-5) 10px" }}>
              <div style={{ fontFamily: "var(--font-display)", fontSize: "var(--text-md)", fontWeight: 600, color: "var(--text-strong)" }}>Notifications</div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                {visible.length > 0 && unread > 0 ? (
                  <button onClick={() => markRead(visible.map((a) => a.id))}
                    style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-brand)", fontSize: "var(--text-xs)", fontWeight: 600, padding: "4px 6px" }}>
                    Mark all read
                  </button>
                ) : null}
                <button onClick={() => setShowSettings((s) => !s)} aria-label="Notification settings"
                  style={{ borderRadius: "var(--radius-sm)", border: "none", background: showSettings ? "var(--surface-sunken)" : "transparent", cursor: "pointer", color: showSettings ? "var(--text-strong)" : "var(--text-brand)", fontSize: "var(--text-xs)", fontWeight: 600, padding: "4px 6px" }}>
                  {showSettings ? "Done" : "Settings"}
                </button>
              </div>
            </div>

            {showSettings ? (
              <div style={{ padding: "0 var(--space-5) var(--space-4)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "4px 0 6px" }}>
                  <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>
                    All notifications
                    <div style={{ fontSize: "var(--text-xs)", fontWeight: 400, color: "var(--text-muted)" }}>{on ? "You'll be alerted before deadlines" : "All notifications are paused"}</div>
                  </div>
                  <Switch checked={on} onChange={(v) => setPrefs((p) => ({ ...p, all: v }))} />
                </div>
                <div style={{ height: 1, background: "var(--border-subtle)", margin: "4px 0" }} />
                {row("deadlines", "Deadline & liability alerts", "Warn me before a window closes.", !on)}
                {row("weekly", "Weekly summary", "A Monday digest of what's open and done.", !on)}
                {row("email", "Email me copies", "Send alerts to " + (executorEmail || "your inbox") + ".", !on)}
              </div>
            ) : (
              <div>
                <div style={{ maxHeight: 360, overflowY: "auto", borderTop: "1px solid var(--border-subtle)" }}>
                  {!on ? (
                    <div style={{ padding: "28px 20px", textAlign: "center", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
                      Notifications are paused. Turn them on in settings.
                    </div>
                  ) : visible.length === 0 ? (
                    <div style={{ padding: "28px 20px", textAlign: "center", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
                      You&apos;re all caught up — no open alerts.
                    </div>
                  ) : (
                    visible.map((a, i) => {
                      const isUnread = !readIds.has(a.id);
                      return (
                        <button key={a.id} onClick={() => markRead([a.id])}
                          style={{ display: "flex", gap: 10, width: "100%", textAlign: "left", padding: "12px 18px", border: "none", borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)", background: isUnread ? "var(--evergreen-50)" : "transparent", cursor: "pointer" }}>
                          <span style={{ flex: "none", marginTop: 6, width: 8, height: 8, borderRadius: "999px", background: SEVERITY_DOT[a.severity] || "var(--text-subtle)" }} />
                          <span style={{ flex: 1, minWidth: 0 }}>
                            <span style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
                              <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{a.title}</span>
                              {typeof a.daysRemaining === "number" ? (
                                <span style={{ flex: "none", fontSize: "var(--text-xs)", fontWeight: 600, color: a.severity === "critical" ? "var(--critical-text, #b03030)" : "var(--text-muted)" }}>{a.daysRemaining}d</span>
                              ) : null}
                            </span>
                            <span style={{ display: "block", fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.5, marginTop: 2 }}>{a.body}</span>
                            {a.actionRequired ? (
                              <span style={{ display: "block", fontSize: "var(--text-xs)", color: "var(--text-brand)", marginTop: 4 }}>{a.actionRequired}</span>
                            ) : null}
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>

                {on ? (
                  <div style={{ padding: "10px 18px", borderTop: "1px solid var(--border-subtle)", background: "var(--paper-50)", display: "flex", flexWrap: "wrap", gap: 14 }}>
                    <button onClick={() => sendEmail("weekly")} disabled={!!sending}
                      style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "none", background: "transparent", cursor: sending ? "default" : "pointer", color: "var(--text-brand)", fontSize: "var(--text-sm)", fontWeight: 600, padding: 0 }}>
                      <I.Send size={14} /> {sending === "weekly" ? "Preparing…" : "Send weekly recap"}
                    </button>
                    {prefs.email && visible.length > 0 ? (
                      <button onClick={() => sendEmail("alerts")} disabled={!!sending}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "none", background: "transparent", cursor: sending ? "default" : "pointer", color: "var(--text-brand)", fontSize: "var(--text-sm)", fontWeight: 600, padding: 0 }}>
                        <I.Send size={14} /> {sending === "alerts" ? "Preparing…" : "Email these alerts"}
                      </button>
                    ) : null}
                    {emailMsg ? <div style={{ width: "100%", fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.5 }}>{emailMsg}</div> : null}
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </React.Fragment>
      ) : null}

      {preview ? (
        <div role="presentation" onClick={() => setPreview(null)}
          style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(17,24,28,0.5)", backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-6)" }}>
          <div role="dialog" aria-modal="true" aria-label="Email preview" onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: 560, maxHeight: "82vh", display: "flex", flexDirection: "column", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-lg)", fontFamily: "var(--font-sans)", overflow: "hidden" }}>
            <div style={{ padding: "var(--space-4) var(--space-5)", borderBottom: "1px solid var(--border-subtle)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ flex: "none", width: 34, height: 34, borderRadius: "var(--radius-md)", background: "var(--evergreen-100)", color: "var(--evergreen-700)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                  <I.Send size={16} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "var(--text-md)", fontWeight: 600, color: "var(--text-strong)" }}>{preview.sent ? "Email sent" : "Email preview"}</div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{previewStatus(preview)}</div>
                </div>
              </div>
            </div>
            <div style={{ padding: "var(--space-4) var(--space-5)", overflowY: "auto" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-subtle)", textTransform: "uppercase", letterSpacing: "var(--tracking-caps)", fontWeight: 700 }}>Subject</div>
              <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)", margin: "2px 0 14px" }}>{preview.subject}</div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-subtle)", textTransform: "uppercase", letterSpacing: "var(--tracking-caps)", fontWeight: 700 }}>Body</div>
              <pre style={{ margin: "6px 0 0", whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", lineHeight: 1.6, color: "var(--text-body)", background: "var(--surface-sunken)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--space-4)" }}>{preview.body}</pre>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, padding: "var(--space-3) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)" }}>
              <button onClick={() => setPreview(null)}
                style={{ border: "1px solid var(--border-default)", background: "var(--surface-card)", borderRadius: "var(--radius-md)", padding: "8px 14px", cursor: "pointer", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
