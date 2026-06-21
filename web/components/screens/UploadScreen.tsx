"use client";

import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import { Badge, Button, Card } from "@/components/ds";
import { deleteDocument, getEstate, parseDocument, parseDocuments } from "@/lib/agentClient";
import {
  DEMO_ESTATE,
  DOC_CHECKLIST,
  ASSET_TYPES,
  SUGGESTED_FIELDS,
  ASSET_KIND,
  fmtMoney,
  type EstateProfile,
  type Asset,
} from "@/lib/design/data";
import type { Asset as EstateAsset } from "@/types/estate";

type Props = { estate?: EstateProfile | null; onDocumentsChanged?: () => void };

type Doc = { id: string; name: string; type: string; documentType: string; parsed: boolean };

const IMAGE_EXT = /\.(png|jpe?g|hei[cf])$/i;

// Offered when auto-detection can't identify a document and the user picks the
// type manually. Values are stored verbatim as the document's documentType.
const DOC_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Select document type" },
  { value: "will", label: "Will or trust" },
  { value: "death_certificate", label: "Death certificate" },
  { value: "letters_testamentary", label: "Letters testamentary" },
  { value: "bank_statement", label: "Bank or brokerage statement" },
  { value: "deed", label: "Property deed" },
  { value: "mortgage_statement", label: "Mortgage or loan statement" },
  { value: "vehicle_title", label: "Vehicle title" },
  { value: "de160_inventory", label: "DE-160 inventory & appraisal" },
  { value: "creditor_notice", label: "Creditor notice" },
  { value: "debt_payment_receipt", label: "Debt payment receipt" },
  { value: "distribution_receipt", label: "Distribution receipt" },
  { value: "tax_return", label: "Tax return" },
  { value: "insurance_policy", label: "Insurance policy" },
  { value: "other", label: "None / supporting document" },
];

function documentTypeLabel(documentType: string) {
  return documentType.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function assetKind(asset: EstateAsset): Asset["kind"] {
  if (asset.type === "real_estate") return "Home";
  if (asset.type === "bank_account" || asset.type === "retirement") return "Bank";
  if (asset.type === "vehicle") return "Car";
  return "Other";
}

function assetTypeLabel(asset: EstateAsset) {
  return asset.type.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function assetFields(asset: EstateAsset) {
  const fields: { label: string; value: string }[] = [];
  if (asset.beneficiaryNamed !== undefined && asset.beneficiaryNamed !== null) {
    fields.push({ label: "Beneficiary named", value: asset.beneficiaryNamed ? "Yes" : "No" });
  }
  if (asset.appraisedValue !== undefined && asset.appraisedValue !== null) {
    fields.push({ label: "Appraised value", value: fmtMoney(asset.appraisedValue) });
  }
  return fields;
}

function fromEstateAsset(asset: EstateAsset): Asset {
  return {
    id: asset.id,
    kind: assetKind(asset),
    type: assetTypeLabel(asset),
    desc: asset.description,
    value: asset.estimatedValue ?? asset.appraisedValue ?? 0,
    appraised: asset.appraised,
    fields: assetFields(asset),
  };
}

function docsFromEstateDocuments(documents: { id: string; fileName: string; documentType: string }[]): Doc[] {
  return documents.map((d) => ({
    id: d.id,
    name: d.fileName,
    type: documentTypeLabel(d.documentType),
    documentType: d.documentType,
    parsed: true,
  }));
}

function seedDocs(): Doc[] {
  return [
    { id: "doc-seed-will", name: "Last Will & Testament.pdf", type: "Will", documentType: "will", parsed: true },
    { id: "doc-seed-bank", name: "Wells Fargo statement, May.pdf", type: "Bank Statement", documentType: "bank_statement", parsed: true },
    { id: "doc-seed-deed", name: "Grant Deed, 1847 Marin Ave.pdf", type: "Deed", documentType: "deed", parsed: true },
  ];
}

const CHECKLIST_ID_BY_DOC_TYPE: Record<string, string> = {
  will: "will",
  bank_statement: "bank",
  deed: "deed",
  death_certificate: "death-cert",
  tax_return: "tax",
  mortgage_statement: "mortgage",
  insurance_policy: "insurance",
  vehicle_title: "vehicle",
};

function checklistIdForDocumentType(documentType: string): string | null {
  return CHECKLIST_ID_BY_DOC_TYPE[documentType] ?? null;
}

function parseProgressLabel(progress: number) {
  if (progress >= 100) return "Document parsed";
  if (progress >= 78) return "Updating the estate profile";
  if (progress >= 48) return "Extracting assets, debts, and people";
  if (progress >= 20) return "Reading pages and classifying the document";
  return "Uploading securely";
}

function ParseProgress({
  fileName,
  progress,
  batchIndex,
  batchTotal,
}: {
  fileName: string | null;
  progress: number;
  batchIndex?: number;
  batchTotal?: number;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(progress)));
  const batchLabel = batchTotal && batchTotal > 1 && batchIndex ? ` ${batchIndex} of ${batchTotal}` : "";
  return (
    <div style={{ maxWidth: 460, margin: "18px auto 0", textAlign: "left" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 14, marginBottom: 8 }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {fileName || "Document"}
          </p>
          <p style={{ margin: "3px 0 0", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{parseProgressLabel(clamped)}{batchLabel}</p>
        </div>
        <span style={{ flex: "none", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)" }}>{clamped}%</span>
      </div>
      <div
        role="progressbar"
        aria-label="Document parsing progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        style={{ height: 8, borderRadius: "var(--radius-full)", background: "var(--surface-sunken)", overflow: "hidden", boxShadow: "inset 0 0 0 1px rgba(203,213,225,0.7)" }}
      >
        <span
          style={{
            display: "block",
            width: `${clamped}%`,
            height: "100%",
            borderRadius: "inherit",
            background: "linear-gradient(90deg, var(--evergreen-500), var(--evergreen-700))",
            transition: "width 420ms cubic-bezier(0.2, 0, 0, 1)",
          }}
        />
      </div>
    </div>
  );
}

// Documents, drop zone + the live estate graph built from parsed documents.
export function UploadScreen({ estate, onDocumentsChanged }: Props) {
  const I = ExecutorIcons;
  const E = DEMO_ESTATE;
  const fmt = fmtMoney;
  const seeded = !estate || estate.seeded;

  const estateId = estate?.id ?? E.id;

  const [docs, setDocs] = React.useState<Doc[]>([]);
  const [drag, setDrag] = React.useState(false);
  const [parsing, setParsing] = React.useState(false);
  const [parseProgress, setParseProgress] = React.useState(0);
  const [parsingFileName, setParsingFileName] = React.useState<string | null>(null);
  const [uploadBatch, setUploadBatch] = React.useState<{ index: number; total: number } | null>(null);
  const [uploadError, setUploadError] = React.useState<string | null>(null);
  const [reviewMessage, setReviewMessage] = React.useState<string | null>(null);
  const [deletingDocId, setDeletingDocId] = React.useState<string | null>(null);
  // Set when auto-detection fails: holds the file awaiting a manual type choice.
  const [pendingFiles, setPendingFiles] = React.useState<File[]>([]);
  const [pendingType, setPendingType] = React.useState<string>(DOC_TYPE_OPTIONS[0].value);
  const [assets, setAssets] = React.useState<Asset[]>([]);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const parseDoneTimer = React.useRef<number | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    getEstate(estateId).then((e) => {
      if (cancelled) return;
      setAssets(e.assets.map(fromEstateAsset));
      setDocs(docsFromEstateDocuments(e.documents));
    }).catch(() => {
      if (cancelled) return;
      setAssets(seeded ? E.assets.map((a) => ({ ...a })) : []);
      setDocs(seeded ? seedDocs() : []);
    });
    return () => { cancelled = true; };
  }, [estateId, seeded, E.assets]);
  const [draftRow, setDraftRow] = React.useState<Asset | null>(null);
  const [naSet, setNaSet] = React.useState<string[]>([]);
  const [openDoc, setOpenDoc] = React.useState<Doc | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const blobUrlMap = React.useRef<Map<string, string>>(new Map());

  React.useEffect(() => {
    const map = blobUrlMap.current;
    return () => { map.forEach((url) => URL.revokeObjectURL(url)); };
  }, []);

  React.useEffect(() => {
    return () => {
      if (parseDoneTimer.current !== null) window.clearTimeout(parseDoneTimer.current);
    };
  }, []);

  React.useEffect(() => {
    if (!parsing) return;
    const timer = window.setInterval(() => {
      setParseProgress((current) => {
        if (current < 18) return current + 5;
        if (current < 48) return current + 4;
        if (current < 78) return current + 2.5;
        if (current < 94) return current + 0.8;
        return current;
      });
    }, 420);
    return () => window.clearInterval(timer);
  }, [parsing]);

  // Persistent URL for the original file, served by the agent from Redis. The
  // seeded demo's documents have no stored bytes, so they fall back to a sample.
  function fileUrl(d: Doc) {
    return `/api/agent/document/${encodeURIComponent(estateId)}/${encodeURIComponent(d.id)}`;
  }

  function downloadDoc(d: Doc) {
    const a = document.createElement("a");
    if (!seeded) {
      a.href = fileUrl(d);
      a.download = d.name;
    } else {
      const body = "EXECUTOR AI — DOCUMENT EXPORT\n\nFile: " + d.name + "\nType: " + d.type + "\nEstate: " + (estate ? estate.deceasedName : E.deceasedName) + "\nStatus: Parsed\n\n(This is a sample export generated by the Executor AI prototype.)\n";
      const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
      a.href = url; a.download = d.name.replace(/\.[a-z]+$/i, "") + ".txt";
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    document.body.appendChild(a); a.click(); a.remove();
  }

  function startEdit(a: Asset) { setEditingId(a.id); setDraftRow({ ...a, fields: (a.fields || []).map((f) => ({ ...f })) }); }
  function cancelEdit() { setEditingId(null); setDraftRow(null); }
  function saveEdit() {
    setAssets((cur) => cur.map((a) => (a.id === editingId && draftRow ? {
      ...draftRow,
      kind: ASSET_KIND[draftRow.type] || "Other",
      value: Number(draftRow.value) || 0,
      fields: (draftRow.fields || []).filter((f) => f.label.trim() || f.value.trim()),
    } : a)));
    cancelEdit();
  }
  function setDraftField(i: number, key: "label" | "value", val: string) { setDraftRow((d) => (d ? { ...d, fields: d.fields.map((f, j) => (j === i ? { ...f, [key]: val } : f)) } : d)); }
  function addDraftField() { setDraftRow((d) => (d ? { ...d, fields: [...(d.fields || []), { label: "", value: "" }] } : d)); }
  function removeDraftField(i: number) { setDraftRow((d) => (d ? { ...d, fields: d.fields.filter((_, j) => j !== i) } : d)); }
  function changeType(type: string) {
    setDraftRow((d) => {
      if (!d) return d;
      const next: Asset = { ...d, type, kind: ASSET_KIND[type] || "Other" };
      if (!d.fields || d.fields.length === 0) next.fields = (SUGGESTED_FIELDS[type] || []).map((label) => ({ label, value: "" }));
      return next;
    });
  }
  function addAsset() {
    const id = "asset-" + Date.now();
    const fields = (SUGGESTED_FIELDS["Bank account"]).map((label) => ({ label, value: "" }));
    setAssets((cur) => [...cur, { id, kind: "Bank", type: "Bank account", desc: "", value: 0, appraised: false, fields }]);
    setEditingId(id);
    setDraftRow({ id, kind: "Bank", type: "Bank account", desc: "", value: 0, appraised: false, fields });
  }
  function deleteAsset(id: string) { setAssets((cur) => cur.filter((a) => a.id !== id)); if (editingId === id) cancelEdit(); }

  async function parseSingleFile(file: File, documentType?: string): Promise<"stored" | "needs_type"> {
    const result = await parseDocument(file, estateId, documentType);
    if (result.needsTypeSelection) return "needs_type";
    setReviewMessage(result.reviewMessage ?? "We found information in this document. Please review it before relying on the estate update.");
    return "stored";
  }

  async function parseBatch(files: File[]): Promise<{
    storedFiles: File[];
    unidentifiedFiles: File[];
    failedFileNames: string[];
    reviewMessages: string[];
  }> {
    const result = await parseDocuments(files, estateId);
    const fileByName = new Map(files.map((file) => [file.name, file]));
    const failedNames = new Set(result.failed.map((failure) => failure.fileName));
    const storedFiles: File[] = [];
    const unidentifiedFiles: File[] = [];
    const reviewMessages: string[] = [];

    for (const parsed of result.results) {
      const file = parsed.fileName ? fileByName.get(parsed.fileName) : undefined;
      if (!file || failedNames.has(file.name)) continue;
      if (parsed.needsTypeSelection) {
        unidentifiedFiles.push(file);
      } else {
        storedFiles.push(file);
        if (parsed.reviewMessage) reviewMessages.push(parsed.reviewMessage);
      }
    }

    return {
      storedFiles,
      unidentifiedFiles,
      failedFileNames: result.failed.map((failure) => failure.fileName),
      reviewMessages,
    };
  }

  async function uploadFiles(files: File[], documentType?: string) {
    const uploadable = files.filter(Boolean);
    if (uploadable.length === 0 || parsing) return;
    setUploadError(null);
    setReviewMessage(null);
    if (parseDoneTimer.current !== null) {
      window.clearTimeout(parseDoneTimer.current);
      parseDoneTimer.current = null;
    }
    setPendingFiles((current) => current.filter((pending) => !uploadable.includes(pending)));
    setParseProgress(6);
    setParsing(true);
    setUploadBatch(uploadable.length > 1 ? { index: 1, total: uploadable.length } : null);
    const storedFiles: File[] = [];
    const unidentifiedFiles: File[] = [];
    const failedFileNames: string[] = [];
    const reviewMessages: string[] = [];
    let parsedAny = false;
    try {
      if (!documentType && uploadable.length > 1) {
        setParsingFileName(`${uploadable.length} documents`);
        setParseProgress(28);
        const batch = await parseBatch(uploadable);
        storedFiles.push(...batch.storedFiles);
        unidentifiedFiles.push(...batch.unidentifiedFiles);
        failedFileNames.push(...batch.failedFileNames);
        reviewMessages.push(...batch.reviewMessages);
        parsedAny = batch.storedFiles.length > 0;
      } else {
        for (let index = 0; index < uploadable.length; index += 1) {
          const file = uploadable[index];
          setParsingFileName(file.name);
          setUploadBatch(uploadable.length > 1 ? { index: index + 1, total: uploadable.length } : null);
          setParseProgress(uploadable.length > 1 ? Math.max(6, Math.round((index / uploadable.length) * 88)) : 6);
          try {
            const status = await parseSingleFile(file, documentType);
            if (status === "needs_type") {
              unidentifiedFiles.push(file);
              continue;
            }
            storedFiles.push(file);
            parsedAny = true;
          } catch (error) {
            console.error(error);
            failedFileNames.push(file.name);
          }
        }
      }
      if (reviewMessages.length > 0) {
        setReviewMessage(reviewMessages.length === 1 ? reviewMessages[0] : `We parsed ${reviewMessages.length} documents. Please review the estate updates before relying on them.`);
      }
      const refreshed = await getEstate(estateId);
      setDocs(docsFromEstateDocuments(refreshed.documents));
      setAssets(refreshed.assets.map(fromEstateAsset));
      for (const file of storedFiles) {
        const newDoc = refreshed.documents.find((d) => d.fileName === file.name);
        if (newDoc && !blobUrlMap.current.has(newDoc.id)) {
          blobUrlMap.current.set(newDoc.id, URL.createObjectURL(file));
        }
      }
      if (unidentifiedFiles.length > 0) {
        setPendingFiles((current) => [...current, ...unidentifiedFiles]);
        setPendingType("");
      }
      setParseProgress(100);
      // Let the shell re-evaluate this estate so chat/letters unlock.
      if (parsedAny) onDocumentsChanged?.();
      if (failedFileNames.length > 0 || unidentifiedFiles.length > 0) {
        const messages: string[] = [];
        if (failedFileNames.length > 0) {
          messages.push(`Couldn't read ${failedFileNames.join(", ")}. Please reupload clearer files.`);
        }
        if (unidentifiedFiles.length > 0) {
          messages.push("Pick a type below for any document we couldn't identify.");
        }
        setUploadError(messages.join(" "));
      }
    } catch (error) {
      console.error(error);
      setUploadError(error instanceof Error ? error.message : "Couldn't read that document. Please try again.");
      setParsing(false);
      setParsingFileName(null);
      setParseProgress(0);
      setUploadBatch(null);
    } finally {
      if (parsedAny || unidentifiedFiles.length > 0 || failedFileNames.length > 0) {
        parseDoneTimer.current = window.setTimeout(() => {
          setParsing(false);
          setParsingFileName(null);
          setParseProgress(0);
          setUploadBatch(null);
          parseDoneTimer.current = null;
        }, 650);
      }
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function confirmPendingType() {
    const [pendingFile] = pendingFiles;
    if (!pendingFile || !pendingType) return;
    void uploadFiles([pendingFile], pendingType);
  }

  function cancelPendingType() {
    setPendingFiles((current) => current.slice(1));
    setUploadError(null);
  }

  function selectedFiles(files: FileList | null | undefined) {
    return Array.from(files ?? []);
  }

  async function removeDocument(doc: Doc) {
    if (seeded) {
      setDocs((current) => current.filter((d) => d.id !== doc.id));
      if (openDoc?.id === doc.id) setOpenDoc(null);
      return;
    }
    if (!window.confirm(`Delete ${doc.name}? This removes the file from this estate.`)) return;
    setDeletingDocId(doc.id);
    setUploadError(null);
    try {
      await deleteDocument(estateId, doc.id);
      blobUrlMap.current.delete(doc.id);
      if (openDoc?.id === doc.id) setOpenDoc(null);
      setDocs((current) => current.filter((d) => d.id !== doc.id));
      const refreshed = await getEstate(estateId);
      setDocs(docsFromEstateDocuments(refreshed.documents).filter((d) => d.id !== doc.id));
      setAssets(refreshed.assets.map(fromEstateAsset));
      onDocumentsChanged?.();
    } catch (error) {
      console.error(error);
      setUploadError(error instanceof Error ? error.message : "Could not delete that document.");
    } finally {
      setDeletingDocId(null);
    }
  }

  const assetIcon: Record<string, typeof I.Home> = { Home: I.Home, Bank: I.Bank, Car: I.Car };
  const uploadedChecklistIds = new Set(
    docs
      .map((doc) => checklistIdForDocumentType(doc.documentType))
      .filter((id): id is string => Boolean(id)),
  );

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "36px 40px", display: "grid", gap: "var(--space-8)" }}>
      <header>
        <h1 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>Documents</h1>
        <p style={{ margin: "8px 0 0", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
          Upload a packet of estate documents. I'll match each file to the checklist and build the estate from it.
        </p>
      </header>

      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (parsing) return;
          const files = selectedFiles(e.dataTransfer.files);
          if (files.length > 0) void uploadFiles(files);
        }}
        onClick={(e) => {
          if (e.target === inputRef.current) return;
          e.preventDefault();
          if (!parsing) inputRef.current?.click();
        }}
        style={{
          display: "block", textAlign: "center", cursor: parsing ? "default" : "pointer", padding: "44px 24px",
          borderRadius: "var(--radius-lg)", border: `1.5px dashed ${drag ? "var(--evergreen-500)" : "var(--border-strong)"}`,
          background: drag ? "var(--evergreen-50)" : "var(--surface-card)", transition: "all var(--transition-fast)",
          opacity: parsing ? 0.7 : 1,
        }}>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/heic,image/heif,.pdf,.jpg,.jpeg,.png,.heic,.heif"
          multiple
          disabled={parsing}
          style={{ display: "none" }}
          onChange={(e) => {
            const files = selectedFiles(e.target.files);
            if (files.length > 0) void uploadFiles(files);
          }}
        />
        <div style={{ display: "inline-flex", width: 48, height: 48, borderRadius: "999px", background: "var(--evergreen-100)", color: "var(--evergreen-700)", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
          <I.Upload size={22} />
        </div>
        <div style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-md)", fontWeight: 600, color: "var(--text-strong)" }}>
          {parsing ? "Reading documents…" : "Drop documents, or click to upload"}
        </div>
        <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginTop: 4 }}>PDF, JPEG, PNG, HEIC, or HEIF. Select as many as you have.</div>
        {parsing ? <ParseProgress fileName={parsingFileName} progress={parseProgress} batchIndex={uploadBatch?.index} batchTotal={uploadBatch?.total} /> : null}
        {uploadError ? (
          <div style={{ fontSize: "var(--text-sm)", color: "var(--critical-text)", marginTop: 10 }}>{uploadError}</div>
        ) : null}
      </label>

      {reviewMessage ? (
        <div style={{
          borderRadius: "var(--radius-lg)", border: "1px solid var(--warning-border)",
          background: "var(--warning-bg)", padding: "16px 18px", display: "flex", gap: 12,
          alignItems: "flex-start", color: "var(--warning-text)",
        }}>
          <I.FileText size={18} style={{ flex: "none", marginTop: 1 }} />
          <div>
            <div style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--text-strong)" }}>
              Review the parse
            </div>
            <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)", lineHeight: "var(--leading-relaxed)" }}>{reviewMessage}</p>
          </div>
        </div>
      ) : null}

      {pendingFiles.length > 0 ? (
        <div style={{
          borderRadius: "var(--radius-lg)", border: "1.5px solid var(--border-strong)",
          background: "var(--surface-card)", padding: "20px 22px", display: "grid", gap: 12,
        }}>
          <div>
            <div style={{ fontFamily: "var(--font-sans)", fontSize: "var(--text-md)", fontWeight: 600, color: "var(--text-strong)" }}>
              We couldn&apos;t identify this document
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginTop: 4 }}>
              Tell us what <strong>{pendingFiles[0].name}</strong> is so we can file it correctly.
              {pendingFiles.length > 1 ? ` ${pendingFiles.length - 1} more file${pendingFiles.length === 2 ? "" : "s"} will be next.` : ""}
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <select
              value={pendingType}
              onChange={(e) => setPendingType(e.target.value)}
              disabled={parsing}
              style={{
                flex: "1 1 240px", minWidth: 0, padding: "9px 12px", borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-strong)", background: "var(--surface-card)",
                fontSize: "var(--text-sm)", color: "var(--text-strong)", cursor: "pointer", appearance: "none",
              }}>
              {DOC_TYPE_OPTIONS.map((opt, index) => (
                <option key={opt.value || "placeholder"} value={opt.value} disabled={index === 0}>{opt.label}</option>
              ))}
            </select>
            <Button onClick={confirmPendingType} disabled={parsing || !pendingType}>
              {parsing ? "Saving…" : "Save document"}
            </Button>
            <Button variant="ghost" onClick={cancelPendingType} disabled={parsing}>Cancel</Button>
          </div>
        </div>
      ) : null}

      <Card title="What to upload" subtitle="Required documents first, then optional ones you only need if they apply to this estate" padded={false}>
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {(DOC_CHECKLIST || []).map((d, i) => {
            const up = uploadedChecklistIds.has(d.id) || (seeded && docs.length === 0 && d.uploaded);
            const na = naSet.includes(d.id);
            const muted = na;
            return (
            <li key={d.id} style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "13px 20px", borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)", opacity: muted ? 0.6 : 1 }}>
              <span style={{ flex: "none", marginTop: 1, color: up ? "var(--success-accent)" : "var(--text-subtle)" }}>
                {up ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
                ) : na ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /></svg>
                )}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)", textDecoration: na ? "line-through" : "none" }}>{d.label}</span>
                  {!d.required && !up ? (
                    <span style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-subtle)" }}>Optional</span>
                  ) : null}
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.5 }}>{d.why}</div>
                {!d.required && !up ? (
                  <button onClick={() => setNaSet((s) => na ? s.filter((x) => x !== d.id) : [...s, d.id])}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--evergreen-50)"; e.currentTarget.style.color = "var(--evergreen-800)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-brand)"; }}
                    style={{ marginTop: 5, marginLeft: -6, padding: "3px 6px", borderRadius: "var(--radius-sm)", border: "none", background: "transparent", cursor: "pointer", fontFamily: "var(--font-sans)", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-brand)", transition: "background var(--transition-fast), color var(--transition-fast)" }}>
                    {na ? "This does apply" : "Mark not applicable"}
                  </button>
                ) : null}
              </div>
              <Badge tone={up ? "success" : na ? "neutral" : d.required ? "warning" : "neutral"}>
                {up ? "Uploaded" : na ? "Not applicable" : d.required ? "Needed" : "If applicable"}
              </Badge>
            </li>
          ); })}
        </ul>
      </Card>

      <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-6)", alignItems: "start" }}>
        <Card title="Uploaded documents" subtitle={`${docs.length} on file`} padded={false}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {docs.length === 0 ? (
              <li style={{ padding: "18px 20px", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>No documents yet. Upload one above to begin.</li>
            ) : docs.map((d, i) => (
              <li key={d.id} style={{ borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)" }}>
                <div
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-sunken)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "13px 14px 13px 20px", transition: "background var(--transition-fast)" }}>
                  <button onClick={() => setOpenDoc(d)}
                    style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0, textAlign: "left", padding: 0, border: "none", background: "transparent", cursor: "pointer" }}>
                    <I.FileText size={18} color="var(--text-subtle)" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-strong)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</div>
                      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{d.type}. Click to open</div>
                    </div>
                  </button>
                  <Badge tone="success">Parsed</Badge>
                  <button
                    type="button"
                    aria-label={`Delete ${d.name}`}
                    title="Delete document"
                    disabled={deletingDocId === d.id}
                    onClick={() => void removeDocument(d)}
                    style={{
                      flex: "none", display: "inline-flex", alignItems: "center", justifyContent: "center",
                      width: 30, height: 30, borderRadius: "var(--radius-sm)", border: "none",
                      background: "transparent", color: "var(--critical-text)", cursor: deletingDocId === d.id ? "default" : "pointer",
                      opacity: deletingDocId === d.id ? 0.5 : 1,
                    }}>
                    <I.X size={16} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Assets" subtitle="Pulled from your documents. Add or adjust as needed." padded={false}
          footer={<Button variant="secondary" size="sm" leadingIcon={<I.Plus size={15} />} onClick={addAsset}>Add asset</Button>}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {assets.length === 0 ? (
              <li style={{ padding: "18px 20px", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>Nothing yet. Upload documents, or add an asset manually below.</li>
            ) : assets.map((a, i) => {
              const Ico = assetIcon[a.kind] || I.FileText;
              const editing = editingId === a.id;
              const border = i === 0 ? "none" : "1px solid var(--border-subtle)";
              const inp: React.CSSProperties = { fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", color: "var(--text-strong)", background: "var(--surface-card)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-sm)", padding: "6px 9px", outline: "none", boxSizing: "border-box" };
              if (editing && draftRow) {
                return (
                  <li key={a.id} style={{ padding: "14px 20px", borderTop: border, background: "var(--evergreen-50)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
                      <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)" }}>Type
                        <select value={draftRow.type} onChange={(e) => changeType(e.target.value)} style={{ ...inp, width: "100%", marginTop: 4, appearance: "none", cursor: "pointer" }}>
                          {ASSET_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                      </label>
                      <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)" }}>Label
                        <input value={draftRow.desc} onChange={(e) => setDraftRow((d) => (d ? { ...d, desc: e.target.value } : d))} placeholder="e.g. Wells Fargo checking …4412" style={{ ...inp, width: "100%", marginTop: 4 }} />
                      </label>
                    </div>

                    <div style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "var(--text-subtle)", margin: "6px 0 6px" }}>Details</div>
                    <div style={{ display: "grid", gap: 6 }}>
                      {(draftRow.fields || []).map((f, fi) => (
                        <div key={fi} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <input value={f.label} onChange={(e) => setDraftField(fi, "label", e.target.value)} placeholder="Field" style={{ ...inp, width: 130, flex: "none", fontWeight: 600, color: "var(--text-muted)" }} />
                          <input value={f.value} onChange={(e) => setDraftField(fi, "value", e.target.value)} placeholder="Value" style={{ ...inp, flex: 1, minWidth: 0 }} />
                          <button onClick={() => removeDraftField(fi)} aria-label="Remove field" style={{ flex: "none", border: "none", background: "transparent", cursor: "pointer", color: "var(--text-subtle)", display: "inline-flex", padding: 4 }}>
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
                          </button>
                        </div>
                      ))}
                      <button onClick={addDraftField} style={{ justifySelf: "start", display: "inline-flex", alignItems: "center", gap: 5, border: "none", background: "transparent", cursor: "pointer", color: "var(--text-brand)", fontFamily: "var(--font-sans)", fontSize: "var(--text-xs)", fontWeight: 600, padding: "2px 0" }}>
                        <I.Plus size={14} /> Add field
                      </button>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
                      <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)" }}>Estimated value</label>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>$</span>
                        <input type="number" value={draftRow.value} onChange={(e) => setDraftRow((d) => (d ? { ...d, value: Number(e.target.value) } : d))} style={{ ...inp, width: 110, fontFamily: "var(--font-mono)", textAlign: "right" }} />
                      </div>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: "var(--text-xs)", color: "var(--text-muted)", cursor: "pointer" }}>
                        <input type="checkbox" checked={draftRow.appraised} onChange={(e) => setDraftRow((d) => (d ? { ...d, appraised: e.target.checked } : d))} />
                        Appraised
                      </label>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 14 }}>
                      <button onClick={() => deleteAsset(a.id)} style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--critical-text)", fontFamily: "var(--font-sans)", fontSize: "var(--text-xs)", fontWeight: 600, padding: 0 }}>Remove asset</button>
                      <div style={{ display: "flex", gap: 6 }}>
                        <Button variant="ghost" size="sm" onClick={cancelEdit}>Cancel</Button>
                        <Button variant="primary" size="sm" leadingIcon={<I.Check size={15} />} onClick={saveEdit}>Save</Button>
                      </div>
                    </div>
                  </li>
                );
              }
              return (
                <li key={a.id} className="asset-row" style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "13px 20px", borderTop: border }}>
                  <Ico size={18} color="var(--text-subtle)" style={{ marginTop: 1 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{a.desc || a.type}</div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: (a.fields && a.fields.length) ? 4 : 0 }}>{a.type}{a.appraised ? "" : " (needs appraisal)"}</div>
                    {(a.fields || []).filter((f) => f.value).map((f, fi) => (
                      <div key={fi} style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", lineHeight: 1.6 }}>
                        <span style={{ color: "var(--text-subtle)" }}>{f.label}: </span>
                        <span style={{ color: "var(--text-body)", fontFamily: /number|VIN|APN/i.test(f.label) ? "var(--font-mono)" : "inherit" }}>{f.value}</span>
                      </div>
                    ))}
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)", whiteSpace: "nowrap" }}>{fmt(a.value)}</span>
                  <button className="asset-edit" aria-label={"Edit " + (a.desc || a.type)} onClick={() => startEdit(a)}
                    style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-subtle)", display: "inline-flex", padding: 5, borderRadius: "var(--radius-sm)" }}>
                    <I.Pencil size={15} />
                  </button>
                </li>
              );
            })}
          </ul>
        </Card>
      </section>

      {openDoc ? (
        <div role="presentation" onClick={() => setOpenDoc(null)}
          style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(17,24,28,0.42)", backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-6)" }}>
          <div role="dialog" aria-modal="true" aria-label={openDoc.name} onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", maxWidth: 560, background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-lg)", fontFamily: "var(--font-sans)", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "var(--space-4) var(--space-5)", borderBottom: "1px solid var(--border-subtle)" }}>
              <span style={{ flex: "none", width: 38, height: 38, borderRadius: "var(--radius-md)", background: "var(--evergreen-100)", color: "var(--evergreen-700)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                <I.FileText size={18} />
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{openDoc.name}</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{openDoc.type}</div>
              </div>
              <Badge tone="success">Parsed</Badge>
            </div>
            <div style={{ padding: "var(--space-6)", background: "var(--surface-sunken)" }}>
              {blobUrlMap.current.has(openDoc.id) ? (
                // Just-uploaded this session: instant preview from the in-memory blob.
                <iframe
                  src={blobUrlMap.current.get(openDoc.id)}
                  title={openDoc.name}
                  style={{ display: "block", width: "100%", height: 420, border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", background: "var(--paper-0)" }}
                />
              ) : !seeded ? (
                // Real estate: the original file is persisted by the agent in Redis.
                IMAGE_EXT.test(openDoc.name) ? (
                  <img src={fileUrl(openDoc)} alt={openDoc.name} style={{ display: "block", maxWidth: "100%", margin: "0 auto", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-sm)" }} />
                ) : (
                  <iframe src={fileUrl(openDoc)} title={openDoc.name} style={{ display: "block", width: "100%", height: 420, border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", background: "var(--paper-0)" }} />
                )
              ) : (
                <div style={{ background: "var(--paper-0)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", boxShadow: "var(--shadow-sm)", padding: "32px 28px", minHeight: 260, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <p style={{ margin: 0, fontSize: "var(--text-sm)", color: "var(--text-muted)", textAlign: "center" }}>Preview only available for documents uploaded in this session.</p>
                </div>
              )}
              <p style={{ margin: "14px 2px 0", fontSize: "var(--text-xs)", color: "var(--text-muted)", textAlign: "center" }}>Preview of the original document. Download to view the full file.</p>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-raised)" }}>
              <Button variant="secondary" onClick={() => setOpenDoc(null)}>Close</Button>
              <Button variant="primary" leadingIcon={<I.Upload size={15} style={{ transform: "rotate(180deg)" }} />} onClick={() => downloadDoc(openDoc)}>Download</Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
