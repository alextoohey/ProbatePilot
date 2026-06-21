"use client";

// Letters, pick a letter type, generate a sign-ready draft.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Card, Button, Select, Badge } from "@/components/ds";
import type { EstateProfile } from "@/lib/design/data";

const I = ExecutorIcons;

type Props = { estate?: EstateProfile };

export function LettersScreen({ estate }: Props) {
  const draftText = `Dana Milligan, Executor
Estate of Robert A. Milligan
1847 Marin Ave, Berkeley, CA 94706

June 20, 2026

UCSF Medical Center
Attn: Patient Accounts

Re: Notice to Creditors, Estate of Robert A. Milligan

To Whom It May Concern:

I am the duly appointed executor of the Estate of Robert A. Milligan, who passed
away on June 3, 2026. Letters testamentary were issued to me on June 10, 2026 by
the Superior Court of California, County of Alameda.

This letter serves as formal notice under California Probate Code §9050 et seq.
If your organization holds a claim against the estate, you must file it with the
court and deliver a copy to me on or before the later of (a) four months after
letters were first issued, or (b) sixty days after this notice was mailed.

Please direct all correspondence regarding this estate to me at the address above.

Sincerely,

Dana Milligan
Executor, Estate of Robert A. Milligan`;

  const [type, setType] = React.useState("Creditor notice, UCSF Medical Center");
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [showPdf, setShowPdf] = React.useState(false);

  function generate() {
    setBusy(true); setDraft("");
    setTimeout(() => { setDraft(draftText); setBusy(false); }, 900);
  }

  function printLetter() {
    const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
    document.body.appendChild(f);
    const doc = f.contentWindow!.document;
    doc.open();
    doc.write('<!DOCTYPE html><html><head><title>' + esc(type) + '</title><style>@page{size:letter;margin:1in;}html,body{margin:0;}body{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:12px;line-height:1.7;color:#1f2933;white-space:pre-wrap;}</style></head><body>' + esc(draft) + '</body></html>');
    doc.close();
    f.contentWindow!.focus();
    setTimeout(() => { f.contentWindow!.print(); setTimeout(() => f.remove(), 1500); }, 350);
  }

  if (estate && !estate.seeded) {
    return (
      <div style={{ maxWidth: 560, margin: "0 auto", padding: "80px 40px", textAlign: "center" }}>
        <span style={{ display: "inline-flex", width: 52, height: 52, borderRadius: "999px", background: "var(--evergreen-100)", color: "var(--evergreen-700)", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
          <I.FileText size={24} />
        </span>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>No letters to draft yet</h1>
        <p style={{ margin: "10px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)" }}>
          Once the estate of {estate.deceasedName} has creditors and accounts on file, I&apos;ll draft sign-ready notices that pull in the right names, dates, and amounts.
        </p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "36px 40px", display: "grid", gap: "var(--space-8)" }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>Letters</h1>
        <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
          I&apos;ll draft sign-ready letters using the estate&apos;s details. Review every word before you send.
        </p>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "var(--space-6)", alignItems: "start" }}>
        <Card title="Generate a letter" padded>
          <div style={{ display: "grid", gap: "var(--space-4)" }}>
            <Select label="Letter type" value={type} onChange={(e) => setType(e.target.value)}
              options={[
                "Creditor notice, UCSF Medical Center",
                "Creditor notice, Chase Visa",
                "Bank notification, Wells Fargo",
                "Beneficiary update letter",
              ]} />
            <Button variant="primary" fullWidth onClick={generate} leadingIcon={<I.Sparkle size={16} />}>
              {busy ? "Drafting…" : "Draft this letter"}
            </Button>
            <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.5 }}>
              Drafts cite the relevant California Probate Code section and pull names, dates, and amounts straight from the estate.
            </p>
          </div>
        </Card>

        <Card title="Draft preview" subtitle={draft ? "Review, edit, then print to sign" : "No draft yet"}
          headerRight={draft ? <Badge tone="brand">Draft</Badge> : null}
          footer={draft ? <div style={{ display: "flex", gap: 8 }}><Button variant="secondary" size="sm" onClick={() => navigator.clipboard && navigator.clipboard.writeText(draft)}>Copy</Button><Button variant="primary" size="sm" leadingIcon={<I.FileText size={15} />} onClick={() => setShowPdf(true)}>Print to sign</Button></div> : null}>
          {draft ? (
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false}
              style={{ display: "block", width: "100%", boxSizing: "border-box", minHeight: 420, resize: "vertical", margin: 0, whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", lineHeight: 1.65, color: "var(--text-body)", background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "var(--space-4)", outline: "none" }} />
          ) : (
            <div style={{ padding: "32px 0", textAlign: "center", color: "var(--text-subtle)" }}>
              <I.FileText size={28} color="var(--text-subtle)" />
              <p style={{ margin: "10px 0 0", fontSize: "var(--text-sm)" }}>Pick a letter type and click &quot;Draft this letter.&quot;</p>
            </div>
          )}
        </Card>
      </section>

      {showPdf ? (
        <div role="presentation" onClick={() => setShowPdf(false)}
          style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(17,24,28,0.55)", backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)", display: "flex", flexDirection: "column", padding: "var(--space-6)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", maxWidth: 720, width: "100%", margin: "0 auto", marginBottom: "var(--space-3)" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--paper-50)", fontFamily: "var(--font-sans)" }}>
              <I.FileText size={16} />
              <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>{type}.pdf</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Button variant="secondary" size="sm" onClick={() => setShowPdf(false)}>Close</Button>
              <Button variant="primary" size="sm" leadingIcon={<I.Upload size={15} style={{ transform: "rotate(180deg)" }} />} onClick={printLetter}>Print / Save as PDF</Button>
            </div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", justifyContent: "center" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ width: "100%", maxWidth: 720, background: "#fff", boxShadow: "var(--shadow-lg)", borderRadius: 2, padding: "72px 80px", boxSizing: "border-box", alignSelf: "flex-start", fontFamily: "var(--font-mono)", fontSize: "13px", lineHeight: 1.75, color: "#1f2933", whiteSpace: "pre-wrap" }}>
              {draft}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
