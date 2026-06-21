import React from "react";

type Severity = "critical" | "warning" | "info" | "success";

function ToneIcon({ tone, size = 16, color = "currentColor" }: { tone: Severity; size?: number; color?: string }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    style: { flex: "none" as const },
  };
  switch (tone) {
    case "critical":
      return (<svg {...common}><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>);
    case "warning":
      return (<svg {...common}><path d="m10.29 3.86-8.18 14.14a2 2 0 0 0 1.71 3h16.36a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>);
    case "info":
      return (<svg {...common}><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>);
    case "success":
      return (<svg {...common}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>);
    default:
      return (<svg {...common}><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>);
  }
}

// ── Alert (DeadlineAgent hero surface) ──────────────────────────────────
export function Alert({
  severity = "critical",
  title,
  children,
  rule,
  daysRemaining,
  timingLabel,
  actionRequired,
  onOpen,
  actionLabel = "View steps",
  onDismiss,
  style,
}: {
  severity?: Severity;
  title?: React.ReactNode;
  children?: React.ReactNode;
  rule?: React.ReactNode;
  daysRemaining?: number;
  timingLabel?: string;
  actionRequired?: React.ReactNode;
  onOpen?: () => void;
  actionLabel?: string;
  onDismiss?: () => void;
  style?: React.CSSProperties;
}) {
  const tones: Record<Severity, { bg: string; bd: string; fg: string; ac: string }> = {
    critical: { bg: "var(--critical-bg)", bd: "var(--critical-border)", fg: "var(--critical-text)", ac: "var(--critical-accent)" },
    warning: { bg: "var(--warning-bg)", bd: "var(--warning-border)", fg: "var(--warning-text)", ac: "var(--warning-accent)" },
    info: { bg: "var(--info-bg)", bd: "var(--info-border)", fg: "var(--info-text)", ac: "var(--info-accent)" },
    success: { bg: "var(--success-bg)", bd: "var(--success-border)", fg: "var(--success-text)", ac: "var(--success-accent)" },
  };
  const t = tones[severity] || tones.critical;
  const clickable = typeof onOpen === "function";

  return (
    <article
      onClick={clickable ? onOpen : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen!(); } } : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      style={{
        position: "relative",
        background: t.bg,
        border: `1px solid ${t.bd}`,
        borderLeft: `3px solid ${t.ac}`,
        borderRadius: "var(--radius-md)",
        padding: "var(--space-4) var(--space-5)",
        fontFamily: "var(--font-sans)",
        color: "var(--text-body)",
        cursor: clickable ? "pointer" : "default",
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-4)" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
            <ToneIcon tone={severity} size={15} color={t.ac} />
            <span style={{ fontSize: "11px", fontWeight: "var(--weight-bold)" as unknown as number, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: t.fg }}>
              {severity}
            </span>
          </div>
          <h3 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-lg)", fontWeight: "var(--weight-semibold)" as unknown as number, color: "var(--text-strong)", letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-snug)" }}>
            {title}
          </h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: "none" }}>
          {timingLabel ? (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)" as unknown as number, color: t.fg, border: `1px solid ${t.bd}`, borderRadius: "var(--radius-full)", padding: "3px 10px", whiteSpace: "nowrap" }}>
              {timingLabel}
            </span>
          ) : typeof daysRemaining === "number" ? (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)" as unknown as number, color: t.fg, border: `1px solid ${t.bd}`, borderRadius: "var(--radius-full)", padding: "3px 10px", whiteSpace: "nowrap" }}>
              {daysRemaining} days
            </span>
          ) : null}
          {onDismiss ? (
            <button type="button" aria-label="Dismiss" onClick={onDismiss} style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-subtle)", display: "inline-flex", padding: 4 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
            </button>
          ) : null}
        </div>
      </div>

      {children ? (
        <p style={{ margin: "10px 0 0", fontSize: "var(--text-sm)", lineHeight: "var(--leading-relaxed)", color: "var(--text-body)" }}>{children}</p>
      ) : null}

      {actionRequired ? (
        <p style={{ margin: "12px 0 0", fontSize: "var(--text-sm)", color: "var(--text-strong)" }}>
          <strong style={{ fontWeight: "var(--weight-semibold)" as unknown as number }}>Next action:</strong> {actionRequired}
        </p>
      ) : null}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-3)", marginTop: rule || onOpen ? "10px" : 0 }}>
        {rule ? (
          <p style={{ margin: 0, fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{rule}</p>
        ) : <span />}
        {clickable ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)" as unknown as number, color: t.fg, whiteSpace: "nowrap" }}>
            {actionLabel}
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
          </span>
        ) : null}
      </div>
    </article>
  );
}

// ── Dialog ──────────────────────────────────────────────────────────────
export function Dialog({
  open,
  title,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  tone = "primary",
}: {
  open: boolean;
  title?: React.ReactNode;
  children?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  onCancel?: () => void;
  tone?: "primary" | "danger";
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && onCancel) onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const confirmBg = tone === "danger" ? "var(--critical-text)" : "var(--action-primary)";

  const btnBase: React.CSSProperties = {
    fontFamily: "var(--font-sans)",
    fontSize: "var(--text-base)",
    fontWeight: "var(--weight-semibold)" as unknown as number,
    padding: "9px 18px",
    borderRadius: "var(--radius-md)",
    cursor: "pointer",
    border: "1px solid transparent",
    transition: "background var(--transition-fast)",
  };

  return (
    <div
      role="presentation"
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(17, 24, 28, 0.42)",
        backdropFilter: "blur(2px)",
        WebkitBackdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-6)",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 440,
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)",
          fontFamily: "var(--font-sans)",
          color: "var(--text-body)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "var(--space-5) var(--space-5) var(--space-4)" }}>
          {title ? (
            <h2 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: "var(--weight-semibold)" as unknown as number, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>
              {title}
            </h2>
          ) : null}
          {children ? (
            <div style={{ marginTop: title ? "8px" : 0, fontSize: "var(--text-base)", lineHeight: "var(--leading-relaxed)", color: "var(--text-muted)" }}>
              {children}
            </div>
          ) : null}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)" }}>
          <button type="button" onClick={onCancel} style={{ ...btnBase, background: "var(--surface-card)", color: "var(--text-strong)", borderColor: "var(--border-default)" }}>
            {cancelLabel}
          </button>
          <button type="button" onClick={onConfirm} style={{ ...btnBase, background: confirmBg, color: "var(--text-inverse)" }}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── ProgressSteps ───────────────────────────────────────────────────────
export function ProgressSteps({ steps = [], current = 0, style }: { steps?: string[]; current?: number; style?: React.CSSProperties }) {
  return (
    <ol style={{ display: "flex", alignItems: "flex-start", listStyle: "none", margin: 0, padding: 0, fontFamily: "var(--font-sans)", ...style }}>
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        const dotBg = done ? "var(--evergreen-700)" : "var(--surface-card)";
        const dotBorder = done ? "var(--evergreen-700)" : active ? "var(--evergreen-500)" : "var(--border-strong)";
        return (
          <li key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, position: "relative", textAlign: "center" }}>
            {i < steps.length - 1 ? (
              <span style={{ position: "absolute", top: 12, left: "50%", width: "100%", height: 2, background: done ? "var(--evergreen-400)" : "var(--border-default)" }} />
            ) : null}
            <span style={{ position: "relative", zIndex: 1, width: 26, height: 26, borderRadius: "999px", background: dotBg, border: `2px solid ${dotBorder}`, display: "inline-flex", alignItems: "center", justifyContent: "center", boxShadow: active ? "var(--shadow-focus)" : "none" }}>
              {done ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
              ) : (
                <span style={{ fontSize: 11, fontWeight: "var(--weight-semibold)" as unknown as number, fontFamily: "var(--font-mono)", color: active ? "var(--evergreen-700)" : "var(--text-subtle)" }}>{i + 1}</span>
              )}
            </span>
            <span style={{ marginTop: 8, fontSize: "var(--text-xs)", fontWeight: (active ? "var(--weight-semibold)" : "var(--weight-regular)") as unknown as number, color: active ? "var(--text-strong)" : done ? "var(--text-muted)" : "var(--text-subtle)", maxWidth: 100, lineHeight: 1.3 }}>
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

// ── Tooltip ─────────────────────────────────────────────────────────────
export function Tooltip({ label, children, side = "top" }: { label: React.ReactNode; children: React.ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  const [open, setOpen] = React.useState(false);
  const pos: Record<string, React.CSSProperties> = {
    top: { bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" },
    bottom: { top: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" },
    right: { left: "calc(100% + 8px)", top: "50%", transform: "translateY(-50%)" },
    left: { right: "calc(100% + 8px)", top: "50%", transform: "translateY(-50%)" },
  };
  return (
    <span
      style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open ? (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            zIndex: 50,
            ...pos[side],
            background: "var(--ink-950)",
            color: "var(--paper-50)",
            fontFamily: "var(--font-sans)",
            fontSize: "var(--text-xs)",
            lineHeight: 1.4,
            padding: "6px 10px",
            borderRadius: "var(--radius-sm)",
            boxShadow: "var(--shadow-md)",
            whiteSpace: "nowrap",
            maxWidth: 240,
            pointerEvents: "none",
          }}
        >
          {label}
        </span>
      ) : null}
    </span>
  );
}

// ── Spinner ─────────────────────────────────────────────────────────────────
export function Spinner({ size = 22, stroke = 2.5, color = "var(--evergreen-600)" }: { size?: number; stroke?: number; color?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      style={{
        display: "inline-block",
        width: size,
        height: size,
        border: `${stroke}px solid var(--border-subtle)`,
        borderTopColor: color,
        borderRadius: "999px",
        animation: "ec-spin 0.7s linear infinite",
      }}
    />
  );
}

// ── ProgressBar ─────────────────────────────────────────────────────────────
// `value` (0–100) renders a determinate bar; omit it for an indeterminate sweep.
export function ProgressBar({ value, label }: { value?: number; label?: string }) {
  const indeterminate = value === undefined || value === null;
  const clamped = indeterminate ? 0 : Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div style={{ width: "100%" }}>
      {label ? (
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{label}</span>
          {!indeterminate ? (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)" }}>{clamped}%</span>
          ) : null}
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={indeterminate ? undefined : clamped}
        style={{ position: "relative", height: 8, borderRadius: "var(--radius-full)", background: "var(--surface-sunken)", overflow: "hidden", boxShadow: "inset 0 0 0 1px var(--border-subtle)" }}
      >
        {indeterminate ? (
          <span
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              width: "40%",
              borderRadius: "inherit",
              background: "linear-gradient(90deg, var(--evergreen-500), var(--evergreen-700))",
              animation: "ec-progress-sweep 1.1s ease-in-out infinite",
            }}
          />
        ) : (
          <span
            style={{
              display: "block",
              width: `${clamped}%`,
              height: "100%",
              borderRadius: "inherit",
              background: "linear-gradient(90deg, var(--evergreen-500), var(--evergreen-700))",
              transition: "width 380ms cubic-bezier(0.2, 0, 0, 1)",
            }}
          />
        )}
      </div>
    </div>
  );
}
