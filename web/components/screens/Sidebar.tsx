"use client";
// App shell sidebar, logo, estate switcher, primary nav, executor profile.
import React from "react";
import { Avatar } from "@/components/ds";
import { ExecutorIcons } from "@/lib/design/icons";
import type { EstateProfile, ExecutorProfile } from "@/lib/design/data";
import { EstateSwitcher } from "./EstateSwitcher";

const I = ExecutorIcons;

type Props = {
  active: string;
  onNavigate: (id: string) => void;
  estates: EstateProfile[];
  activeEstateId: string;
  onSwitchEstate: (id: string) => void;
  onCreateEstate: () => void;
  profile: ExecutorProfile;
  onEditProfile: () => void;
  onLogout: () => void;
};

export function Sidebar({ active, onNavigate, estates, activeEstateId, onSwitchEstate, onCreateEstate, profile, onEditProfile, onLogout }: Props) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const nav = [
    { id: "dashboard", label: "Dashboard", icon: I.Dashboard },
    { id: "documents", label: "Documents", icon: I.Upload },
    { id: "chat", label: "Estate chat", icon: I.Chat },
    { id: "letters", label: "Letters", icon: I.FileText },
  ];

  return (
    <aside style={{ width: 248, flex: "none", background: "var(--paper-50)", borderRight: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "18px 20px 14px" }}>
        <img src="/assets/logomark.svg" alt="" style={{ width: 28, height: 28 }} />
        <span style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 600, letterSpacing: "-0.4px", color: "var(--text-strong)" }}>
          Executor<b style={{ fontFamily: "var(--font-sans)", fontWeight: 700, color: "var(--text-brand)" }}> AI</b>
        </span>
      </div>

      <EstateSwitcher estates={estates} activeId={activeEstateId} onSwitch={onSwitchEstate} onCreate={onCreateEstate} />

      <nav style={{ display: "flex", flexDirection: "column", gap: 2, padding: "8px 12px" }}>
        {nav.map((n) => {
          const on = active === n.id;
          return (
            <button
              key={n.id}
              onClick={() => onNavigate(n.id)}
              style={{
                display: "flex", alignItems: "center", gap: 12, width: "100%", textAlign: "left",
                padding: "9px 12px", borderRadius: "var(--radius-md)", border: "none", cursor: "pointer",
                background: on ? "var(--evergreen-100)" : "transparent",
                color: on ? "var(--evergreen-800)" : "var(--text-muted)",
                fontFamily: "var(--font-sans)", fontSize: "var(--text-base)", fontWeight: on ? 600 : 500,
                transition: "background var(--transition-fast)",
              }}
            >
              <n.icon size={18} />
              {n.label}
            </button>
          );
        })}
      </nav>

      <div style={{ marginTop: "auto", position: "relative", borderTop: "1px solid var(--border-subtle)" }}>
        <button onClick={() => setMenuOpen((o) => !o)} aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Your account"
          style={{ padding: 14, display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", background: menuOpen ? "var(--surface-sunken)" : "transparent", border: "none", cursor: "pointer", transition: "background var(--transition-fast)" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-sunken)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = menuOpen ? "var(--surface-sunken)" : "transparent")}>
          <Avatar name={profile.name} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{profile.name}</div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{profile.email}</div>
          </div>
          <span style={{ color: "var(--text-subtle)", display: "inline-flex" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="m18 15-6-6-6 6" /></svg>
          </span>
        </button>

        {menuOpen ? (
          <React.Fragment>
            <div onClick={() => setMenuOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
            <div role="menu" style={{ position: "absolute", bottom: "calc(100% - 6px)", left: 12, right: 12, zIndex: 50, background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", padding: 6, fontFamily: "var(--font-sans)" }}>
              <button role="menuitem" onClick={() => { setMenuOpen(false); onEditProfile(); }}
                style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", padding: "9px 10px", borderRadius: "var(--radius-sm)", border: "none", background: "transparent", cursor: "pointer", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-body)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-sunken)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                Edit profile
              </button>
              <button role="menuitem" onClick={() => { setMenuOpen(false); onLogout(); }}
                style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", padding: "9px 10px", borderRadius: "var(--radius-sm)", border: "none", background: "transparent", cursor: "pointer", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--critical-text)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--critical-bg)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
                Log out
              </button>
            </div>
          </React.Fragment>
        ) : null}
      </div>
    </aside>
  );
}
