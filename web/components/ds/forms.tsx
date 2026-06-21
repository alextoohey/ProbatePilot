import React from "react";

// ── Checkbox ────────────────────────────────────────────────────────────
export function Checkbox({
  label,
  checked,
  onChange,
  disabled = false,
  id,
  style,
}: {
  label?: React.ReactNode;
  checked?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
  id?: string;
  style?: React.CSSProperties;
}) {
  const inputId = id || (typeof label === "string" ? `cb-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  return (
    <label
      htmlFor={inputId}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "10px",
        fontFamily: "var(--font-sans)",
        fontSize: "var(--text-base)",
        color: disabled ? "var(--text-subtle)" : "var(--text-body)",
        cursor: disabled ? "not-allowed" : "pointer",
        ...style,
      }}
    >
      <span
        style={{
          width: 18,
          height: 18,
          flex: "none",
          borderRadius: "var(--radius-sm)",
          border: `1px solid ${checked ? "var(--evergreen-700)" : "var(--border-strong)"}`,
          background: checked ? "var(--evergreen-700)" : "var(--surface-card)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background var(--transition-fast), border-color var(--transition-fast)",
        }}
      >
        {checked ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
        ) : null}
      </span>
      <input
        id={inputId}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        style={{ position: "absolute", opacity: 0, width: 0, height: 0 }}
      />
      {label}
    </label>
  );
}

// ── Input ───────────────────────────────────────────────────────────────
export function Input({
  label,
  hint,
  error,
  leadingIcon = null,
  id,
  style,
  ...rest
}: {
  label?: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  leadingIcon?: React.ReactNode;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const inputId = id || (label ? `in-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const [focus, setFocus] = React.useState(false);
  const borderColor = error ? "var(--critical-border)" : focus ? "var(--border-brand)" : "var(--border-default)";

  return (
    <div style={{ fontFamily: "var(--font-sans)", ...style }}>
      {label ? (
        <label htmlFor={inputId} style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)" as unknown as number, color: "var(--text-strong)", marginBottom: "6px" }}>
          {label}
        </label>
      ) : null}
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        {leadingIcon ? (
          <span style={{ position: "absolute", left: 12, display: "inline-flex", color: "var(--text-subtle)", pointerEvents: "none" }}>{leadingIcon}</span>
        ) : null}
        <input
          id={inputId}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: "100%",
            boxSizing: "border-box",
            fontFamily: "var(--font-sans)",
            fontSize: "var(--text-base)",
            color: "var(--text-body)",
            background: "var(--surface-card)",
            border: `1px solid ${borderColor}`,
            borderRadius: "var(--radius-md)",
            padding: leadingIcon ? "9px 12px 9px 36px" : "9px 12px",
            outline: "none",
            boxShadow: focus ? "var(--shadow-focus)" : "none",
            transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
          }}
          {...rest}
        />
      </div>
      {error ? (
        <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--critical-text)" }}>{error}</p>
      ) : hint ? (
        <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{hint}</p>
      ) : null}
    </div>
  );
}

// ── Select ──────────────────────────────────────────────────────────────
type SelectOption = string | { value: string; label: string };

export function Select({
  label,
  hint,
  options = [],
  id,
  style,
  ...rest
}: {
  label?: string;
  hint?: React.ReactNode;
  options?: SelectOption[];
} & React.SelectHTMLAttributes<HTMLSelectElement>) {
  const inputId = id || (label ? `sel-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ fontFamily: "var(--font-sans)", ...style }}>
      {label ? (
        <label htmlFor={inputId} style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)" as unknown as number, color: "var(--text-strong)", marginBottom: "6px" }}>
          {label}
        </label>
      ) : null}
      <div style={{ position: "relative" }}>
        <select
          id={inputId}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: "100%",
            boxSizing: "border-box",
            appearance: "none",
            WebkitAppearance: "none",
            fontFamily: "var(--font-sans)",
            fontSize: "var(--text-base)",
            color: "var(--text-body)",
            background: "var(--surface-card)",
            border: `1px solid ${focus ? "var(--border-brand)" : "var(--border-default)"}`,
            borderRadius: "var(--radius-md)",
            padding: "9px 36px 9px 12px",
            outline: "none",
            cursor: "pointer",
            boxShadow: focus ? "var(--shadow-focus)" : "none",
            transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
          }}
          {...rest}
        >
          {options.map((o) =>
            typeof o === "string" ? (
              <option key={o} value={o}>{o}</option>
            ) : (
              <option key={o.value} value={o.value}>{o.label}</option>
            )
          )}
        </select>
        <span style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--text-subtle)", display: "inline-flex" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
        </span>
      </div>
      {hint ? <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{hint}</p> : null}
    </div>
  );
}

// ── Textarea ────────────────────────────────────────────────────────────
export function Textarea({
  label,
  hint,
  error,
  rows = 4,
  id,
  style,
  ...rest
}: {
  label?: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
} & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const inputId = id || (label ? `ta-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const [focus, setFocus] = React.useState(false);
  const borderColor = error ? "var(--critical-border)" : focus ? "var(--border-brand)" : "var(--border-default)";
  return (
    <div style={{ fontFamily: "var(--font-sans)", ...style }}>
      {label ? (
        <label htmlFor={inputId} style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)" as unknown as number, color: "var(--text-strong)", marginBottom: "6px" }}>
          {label}
        </label>
      ) : null}
      <textarea
        id={inputId}
        rows={rows}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        style={{
          width: "100%",
          boxSizing: "border-box",
          fontFamily: "var(--font-sans)",
          fontSize: "var(--text-base)",
          lineHeight: "var(--leading-normal)",
          color: "var(--text-body)",
          background: "var(--surface-card)",
          border: `1px solid ${borderColor}`,
          borderRadius: "var(--radius-md)",
          padding: "10px 12px",
          outline: "none",
          resize: "vertical",
          boxShadow: focus ? "var(--shadow-focus)" : "none",
          transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
        }}
        {...rest}
      />
      {error ? (
        <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--critical-text)" }}>{error}</p>
      ) : hint ? (
        <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{hint}</p>
      ) : null}
    </div>
  );
}
