import React from "react";

// ── Avatar ──────────────────────────────────────────────────────────────
export function Avatar({
  name = "",
  initials,
  size = "md",
  tone = "brand",
  style,
}: {
  name?: string;
  initials?: string;
  size?: "sm" | "md" | "lg";
  tone?: "brand" | "neutral" | "ink";
  style?: React.CSSProperties;
}) {
  const dims = { sm: 28, md: 36, lg: 48 } as const;
  const fontSize = { sm: 11, md: 13, lg: 17 } as const;
  const d = dims[size] || dims.md;
  const text = initials || name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

  const tones = {
    brand: { bg: "var(--evergreen-100)", fg: "var(--evergreen-800)" },
    neutral: { bg: "var(--surface-sunken)", fg: "var(--text-muted)" },
    ink: { bg: "var(--ink-700)", fg: "var(--paper-50)" },
  } as const;
  const t = tones[tone] || tones.brand;

  return (
    <span
      style={{
        width: d,
        height: d,
        flex: "none",
        borderRadius: "999px",
        background: t.bg,
        color: t.fg,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "var(--font-sans)",
        fontSize: fontSize[size] || 13,
        fontWeight: "var(--weight-semibold)" as unknown as number,
        letterSpacing: "0.02em",
        ...style,
      }}
      aria-label={name || undefined}
    >
      {text}
    </span>
  );
}

// ── KeyValue ────────────────────────────────────────────────────────────
export type KeyValueItem = { label: React.ReactNode; value: React.ReactNode; mono?: boolean };

export function KeyValue({ items = [], style }: { items?: KeyValueItem[]; style?: React.CSSProperties }) {
  return (
    <dl style={{ margin: 0, fontFamily: "var(--font-sans)", ...style }}>
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: "var(--space-4)",
            padding: "10px 0",
            borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)",
          }}
        >
          <dt style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", flex: "none" }}>{it.label}</dt>
          <dd
            style={{
              margin: 0,
              fontSize: "var(--text-sm)",
              fontWeight: "var(--weight-medium)" as unknown as number,
              color: "var(--text-strong)",
              fontFamily: it.mono ? "var(--font-mono)" : "var(--font-sans)",
              textAlign: "right",
            }}
          >
            {it.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// ── StatBlock ───────────────────────────────────────────────────────────
export function StatBlock({
  label,
  value,
  sub,
  tone = "default",
  style,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "default" | "brand" | "critical" | "success";
  style?: React.CSSProperties;
}) {
  const valueColor =
    ({
      default: "var(--text-strong)",
      brand: "var(--text-brand)",
      critical: "var(--critical-text)",
      success: "var(--success-text)",
    } as const)[tone] || "var(--text-strong)";

  return (
    <div style={{ fontFamily: "var(--font-sans)", ...style }}>
      <p style={{ margin: 0, fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)" as unknown as number, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-muted)" }}>
        {label}
      </p>
      <p style={{ margin: "6px 0 0", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)" as unknown as number, letterSpacing: "var(--tracking-tight)", lineHeight: 1, color: valueColor }}>
        {value}
      </p>
      {sub ? <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{sub}</p> : null}
    </div>
  );
}
