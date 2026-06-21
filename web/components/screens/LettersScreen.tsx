"use client";

// Letters, pick a letter type, generate a sign-ready draft.
import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Card, Button, Select, ProgressBar } from "@/components/ds";
import type { EstateProfile } from "@/lib/design/data";
import { generateLetter, getEstate } from "@/lib/agentClient";

const I = ExecutorIcons;

type Props = { estate?: EstateProfile };

// Backend-supported letter types (agent/prompts/letters.py). The `value` is the
// enum the API expects; `label` is what the executor sees.
const LETTER_TYPES: { value: string; label: string }[] = [
  { value: "creditor_notice", label: "Creditor notice" },
  { value: "bank_notification", label: "Bank notification" },
  { value: "irs_ein_request", label: "IRS EIN request" },
  { value: "beneficiary_update", label: "Beneficiary update" },
  { value: "property_transfer", label: "Property transfer" },
  { value: "custom", label: "Custom letter…" },
];

// Which letter types are addressed to a specific person/organization, and where
// to source the candidate recipients from in the estate state.
const RECIPIENT_SOURCE: Record<string, "creditors" | "beneficiaries"> = {
  creditor_notice: "creditors",
  bank_notification: "creditors",
  beneficiary_update: "beneficiaries",
};

export function LettersScreen({ estate }: Props) {
  const estateId = estate?.id ?? "";

  const [type, setType] = React.useState(LETTER_TYPES[0].value);
  const [recipient, setRecipient] = React.useState("");
  const [customRecipient, setCustomRecipient] = React.useState("");
  const [instructions, setInstructions] = React.useState("");
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showPdf, setShowPdf] = React.useState(false);
  const [creditors, setCreditors] = React.useState<string[]>([]);
  const [beneficiaries, setBeneficiaries] = React.useState<string[]>([]);
  const [progress, setProgress] = React.useState(0);

  // Simulated drafting progress — there's no token-level signal from the
  // single-shot letter call, so we ramp toward ~92% while busy and reset after.
  React.useEffect(() => {
    if (!busy) { setProgress(0); return; }
    setProgress(10);
    const id = window.setInterval(() => {
      setProgress((p) => (p < 92 ? p + Math.max(1, Math.round((92 - p) / 10)) : p));
    }, 280);
    return () => window.clearInterval(id);
  }, [busy]);

  function copyDraft() { navigator.clipboard?.writeText(draft); }

  const isCustom = type === "custom";
  const typeLabel = LETTER_TYPES.find((t) => t.value === type)?.label ?? type;
  const recipientSource = RECIPIENT_SOURCE[type];
  const recipientOptions = recipientSource === "beneficiaries" ? beneficiaries : creditors;
  // Custom letters need a description to draft from.
  const canGenerate = !busy && !!estateId && (!isCustom || instructions.trim().length > 0);

  // Pull the real creditors and beneficiaries so the recipient list reflects
  // this estate's parsed documents instead of hardcoded names.
  React.useEffect(() => {
    if (!estateId) return;
    let cancelled = false;
    getEstate(estateId)
      .then((e) => {
        if (cancelled) return;
        setCreditors(e.debts.map((d) => d.creditor).filter(Boolean));
        setBeneficiaries(e.beneficiaries.map((b) => b.name).filter(Boolean));
      })
      .catch(() => {
        /* leave recipient lists empty; the backend still drafts with a generic recipient */
      });
    return () => { cancelled = true; };
  }, [estateId]);

  // Reset the chosen recipient whenever the letter type (and therefore the
  // candidate list) changes.
  React.useEffect(() => { setRecipient(""); }, [type]);

  async function generate() {
    if (!canGenerate) return;
    const recipientName = isCustom ? customRecipient.trim() || undefined : recipient || undefined;
    setBusy(true); setDraft(""); setError(null);
    try {
      const res = await generateLetter(type, estateId, recipientName, isCustom ? instructions.trim() : undefined);
      setDraft(res.draft);
    } catch (e) {
      setError(e instanceof Error ? e.message : "I couldn't draft that letter. Make sure the agent is running, then try again.");
    } finally {
      setBusy(false);
    }
  }

  function printLetter() {
    const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
    document.body.appendChild(f);
    const doc = f.contentWindow!.document;
    doc.open();
    doc.write('<!DOCTYPE html><html><head><title>' + esc(typeLabel) + '</title><style>@page{size:letter;margin:1in;}html,body{margin:0;}body{font-family:"Times New Roman",serif;font-size:12px;line-height:1.75;color:#1f2933;white-space:pre-wrap;}</style></head><body>' + esc(draft) + '</body></html>')
    doc.close();
    f.contentWindow!.focus();
    setTimeout(() => { f.contentWindow!.print(); setTimeout(() => f.remove(), 1500); }, 350);
  }

  if (estate && !estate.hasDocuments) {
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
              options={LETTER_TYPES} />
            {isCustom ? (
              <>
                <label style={{ display: "grid", gap: 6, fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-strong)" }}>
                  What should this letter do?
                  <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={4}
                    placeholder="e.g. Ask the county assessor's office to reassess the Marin Ave property under the parent–child exclusion."
                    style={{ resize: "vertical", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", lineHeight: 1.5, color: "var(--text-body)", background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "10px 12px", outline: "none", boxSizing: "border-box" }} />
                </label>
                <label style={{ display: "grid", gap: 6, fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-strong)" }}>
                  Recipient (optional)
                  <input value={customRecipient} onChange={(e) => setCustomRecipient(e.target.value)}
                    placeholder="e.g. Alameda County Assessor's Office"
                    style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", color: "var(--text-body)", background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", padding: "9px 12px", outline: "none", boxSizing: "border-box" }} />
                </label>
              </>
            ) : recipientSource && recipientOptions.length > 0 ? (
              <Select label="Recipient" value={recipient} onChange={(e) => setRecipient(e.target.value)}
                options={[{ value: "", label: "Choose a recipient…" }, ...recipientOptions.map((r) => ({ value: r, label: r }))]} />
            ) : null}
            <Button variant="primary" fullWidth onClick={generate} disabled={!canGenerate} leadingIcon={<I.Sparkle size={16} />}>
              {busy ? "Drafting…" : "Draft this letter"}
            </Button>
            {error ? (
              <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--critical-text)", lineHeight: 1.5 }}>{error}</p>
            ) : null}
            <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.5 }}>
              Drafts cite the relevant California Probate Code section and pull names, dates, and amounts straight from the estate.
            </p>
          </div>
        </Card>

        <Card title="Draft preview" subtitle={draft ? "Edit any wording, then print or copy to send" : "No draft yet"}
          headerRight={null}
          footer={draft ? <div style={{ display: "flex", gap: 8 }}><Button variant="secondary" size="sm" onClick={copyDraft}>Copy as plain text</Button><Button variant="primary" size="sm" leadingIcon={<I.FileText size={15} />} onClick={() => setShowPdf(true)}>Print to sign</Button></div> : null}>
          {busy ? (
            <div style={{ padding: "48px var(--space-5)", display: "grid", gap: 12, placeItems: "center" }}>
              <div style={{ width: "100%", maxWidth: 420 }}>
                <ProgressBar value={progress} label="Drafting your letter…" />
              </div>
              <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--text-muted)", textAlign: "center" }}>
                Pulling the right names, dates, and amounts from the estate.
              </p>
            </div>
          ) : draft ? (
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false}
              aria-label="Letter draft"
              style={{ display: "block", width: "100%", boxSizing: "border-box", minHeight: 460, resize: "vertical", margin: 0, padding: "var(--space-5)", fontFamily: "Georgia, serif", fontSize: "var(--text-sm)", lineHeight: 1.8, color: "var(--text-body)", background: "var(--surface-card)", border: "none", borderRadius: "var(--radius-md)", outline: "none", whiteSpace: "pre-wrap" }} />
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
              <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>{typeLabel}.pdf</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Button variant="secondary" size="sm" onClick={() => setShowPdf(false)}>Close</Button>
              <Button variant="primary" size="sm" leadingIcon={<I.Upload size={15} style={{ transform: "rotate(180deg)" }} />} onClick={printLetter}>Print / Save as PDF</Button>
            </div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", justifyContent: "center" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ width: "100%", maxWidth: 720, background: "#fff", boxShadow: "var(--shadow-lg)", borderRadius: 2, padding: "72px 80px", boxSizing: "border-box", alignSelf: "flex-start", fontFamily: "Georgia, serif", fontSize: "13px", lineHeight: 1.75, color: "#1f2933", whiteSpace: "pre-wrap" }}>
              {draft}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
