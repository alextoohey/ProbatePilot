import React from "react";

// ── Severity glyph shared by Badge ──────────────────────────────────────
type Tone = "neutral" | "critical" | "warning" | "info" | "success" | "brand";

function ToneIcon({ tone, size = 13, color = "currentColor" }: { tone: Tone; size?: number; color?: string }) {
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
    case "brand":
      return (<svg {...common}><path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z" /></svg>);
    default:
      return (<svg {...common}><circle cx="12" cy="12" r="9" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>);
  }
}

// ── Badge ───────────────────────────────────────────────────────────────
export function Badge({
  children,
  tone = "neutral",
  dot = false,
  style,
  ...rest
}: { children?: React.ReactNode; tone?: Tone; dot?: boolean } & React.HTMLAttributes<HTMLSpanElement>) {
  const tones: Record<Tone, { bg: string; bd: string; fg: string; ac: string }> = {
    neutral: { bg: "var(--surface-sunken)", bd: "var(--border-subtle)", fg: "var(--text-muted)", ac: "var(--ink-400)" },
    critical: { bg: "var(--critical-bg)", bd: "var(--critical-border)", fg: "var(--critical-text)", ac: "var(--critical-accent)" },
    warning: { bg: "var(--warning-bg)", bd: "var(--warning-border)", fg: "var(--warning-text)", ac: "var(--warning-accent)" },
    info: { bg: "var(--info-bg)", bd: "var(--info-border)", fg: "var(--info-text)", ac: "var(--info-accent)" },
    success: { bg: "var(--success-bg)", bd: "var(--success-border)", fg: "var(--success-text)", ac: "var(--success-accent)" },
    brand: { bg: "var(--evergreen-100)", bd: "var(--evergreen-200)", fg: "var(--evergreen-800)", ac: "var(--evergreen-500)" },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontFamily: "var(--font-sans)",
        fontSize: "11px",
        fontWeight: "var(--weight-semibold)" as unknown as number,
        letterSpacing: "var(--tracking-caps)",
        textTransform: "uppercase",
        padding: "3px 9px",
        borderRadius: "var(--radius-full)",
        background: t.bg,
        border: `1px solid ${t.bd}`,
        color: t.fg,
        whiteSpace: "nowrap",
        ...style,
      }}
      {...rest}
    >
      {dot ? <ToneIcon tone={tone} size={13} color={t.ac} /> : null}
      {children}
    </span>
  );
}

// ── Button ──────────────────────────────────────────────────────────────
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  fullWidth = false,
  leadingIcon = null,
  trailingIcon = null,
  type = "button",
  onClick,
  style,
  ...rest
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const sizes: Record<ButtonSize, { fontSize: string; padding: string; gap: string; height: number }> = {
    sm: { fontSize: "var(--text-sm)", padding: "6px 12px", gap: "6px", height: 32 },
    md: { fontSize: "var(--text-base)", padding: "9px 16px", gap: "8px", height: 40 },
    lg: { fontSize: "var(--text-md)", padding: "12px 22px", gap: "10px", height: 48 },
  };
  const s = sizes[size] || sizes.md;

  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: s.gap,
    fontFamily: "var(--font-sans)",
    fontWeight: "var(--weight-semibold)" as unknown as number,
    fontSize: s.fontSize,
    lineHeight: 1,
    padding: s.padding,
    minHeight: s.height,
    width: fullWidth ? "100%" : "auto",
    borderRadius: "var(--radius-md)",
    border: "1px solid transparent",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.55 : 1,
    transition: "background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast)",
    whiteSpace: "nowrap",
    userSelect: "none",
  };

  const variants: Record<ButtonVariant, React.CSSProperties> = {
    primary: { background: "var(--action-primary)", color: "var(--text-inverse)" },
    secondary: { background: "var(--surface-card)", color: "var(--text-strong)", borderColor: "var(--border-default)" },
    ghost: { background: "transparent", color: "var(--text-brand)" },
    danger: { background: "var(--surface-card)", color: "var(--critical-text)", borderColor: "var(--critical-border)" },
  };

  const hovers: Record<ButtonVariant, React.CSSProperties> = {
    primary: { background: "var(--action-primary-hover)" },
    secondary: { background: "var(--surface-sunken)" },
    ghost: { background: "var(--evergreen-50)" },
    danger: { background: "var(--critical-bg)" },
  };

  const [hover, setHover] = React.useState(false);
  const styleNow: React.CSSProperties = {
    ...base,
    ...variants[variant],
    ...(hover && !disabled ? hovers[variant] : null),
    ...style,
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={styleNow}
      {...rest}
    >
      {leadingIcon}
      {children}
      {trailingIcon}
    </button>
  );
}

// ── Card ────────────────────────────────────────────────────────────────
export function Card({
  children,
  title,
  subtitle,
  headerRight = null,
  footer = null,
  padded = true,
  tint = false,
  style,
  ...rest
}: {
  children?: React.ReactNode;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  headerRight?: React.ReactNode;
  footer?: React.ReactNode;
  padded?: boolean;
  tint?: boolean;
} & React.HTMLAttributes<HTMLElement>) {
  const hasHeader = title || subtitle || headerRight;
  return (
    <section
      style={{
        background: tint ? "var(--surface-tint)" : "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        overflow: "hidden",
        fontFamily: "var(--font-sans)",
        color: "var(--text-body)",
        ...style,
      }}
      {...rest}
    >
      {hasHeader ? (
        <header
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "var(--space-4)",
            padding: "var(--space-4) var(--space-5)",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div>
            {title ? (
              <h3 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-lg)", fontWeight: "var(--weight-semibold)" as unknown as number, color: "var(--text-strong)", letterSpacing: "var(--tracking-tight)" }}>
                {title}
              </h3>
            ) : null}
            {subtitle ? (
              <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{subtitle}</p>
            ) : null}
          </div>
          {headerRight}
        </header>
      ) : null}
      <div style={{ padding: padded ? "var(--space-5)" : 0 }}>{children}</div>
      {footer ? (
        <footer style={{ padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)" }}>
          {footer}
        </footer>
      ) : null}
    </section>
  );
}

// ── IconButton ──────────────────────────────────────────────────────────
export function IconButton({
  children,
  variant = "ghost",
  size = "md",
  disabled = false,
  onClick,
  style,
  "aria-label": ariaLabel,
  ...rest
}: {
  variant?: "ghost" | "outline" | "solid";
  size?: "sm" | "md" | "lg";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const dims = { sm: 30, md: 38, lg: 44 } as const;
  const d = dims[size] || dims.md;
  const [hover, setHover] = React.useState(false);

  const variants = {
    ghost: { background: "transparent", color: "var(--text-muted)", border: "1px solid transparent" },
    outline: { background: "var(--surface-card)", color: "var(--text-strong)", border: "1px solid var(--border-default)" },
    solid: { background: "var(--action-primary)", color: "var(--text-inverse)", border: "1px solid transparent" },
  } as const;
  const hovers = {
    ghost: { background: "var(--surface-sunken)", color: "var(--text-strong)" },
    outline: { background: "var(--surface-sunken)" },
    solid: { background: "var(--action-primary-hover)" },
  } as const;

  return (
    <button
      type="button"
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width: d,
        height: d,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--radius-md)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "background var(--transition-fast), color var(--transition-fast)",
        ...variants[variant],
        ...(hover && !disabled ? hovers[variant] : null),
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}

// ── Tag ─────────────────────────────────────────────────────────────────
export function Tag({
  children,
  icon = null,
  onRemove,
  style,
  ...rest
}: {
  children?: React.ReactNode;
  icon?: React.ReactNode;
  onRemove?: () => void;
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontFamily: "var(--font-sans)",
        fontSize: "var(--text-sm)",
        fontWeight: "var(--weight-medium)" as unknown as number,
        color: "var(--text-body)",
        padding: "4px 10px",
        borderRadius: "var(--radius-full)",
        background: "var(--surface-card)",
        border: "1px solid var(--border-default)",
        whiteSpace: "nowrap",
        ...style,
      }}
      {...rest}
    >
      {icon ? <span style={{ display: "inline-flex", color: "var(--text-muted)" }}>{icon}</span> : null}
      {children}
      {onRemove ? (
        <button
          type="button"
          aria-label="Remove"
          onClick={onRemove}
          style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-subtle)", display: "inline-flex", padding: 0, marginLeft: 2, fontSize: 14, lineHeight: 1 }}
        >
          ×
        </button>
      ) : null}
    </span>
  );
}
