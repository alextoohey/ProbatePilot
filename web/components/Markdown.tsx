"use client";

// A small, dependency-free Markdown renderer for chat replies. It covers what
// Claude actually emits in conversation — paragraphs, **bold**, *italic*,
// `inline code`, bullet/numbered lists, headings, and links — without pulling in
// a full markdown library. Anything it doesn't recognize renders as plain text.
import React from "react";

const codeStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: "0.92em",
  background: "var(--surface-sunken)",
  border: "1px solid var(--border-subtle)",
  borderRadius: "var(--radius-sm)",
  padding: "1px 5px",
};

const linkStyle: React.CSSProperties = { color: "var(--text-brand)", textDecoration: "underline" };

// Inline spans: code first (so markers inside code aren't reparsed), then bold,
// italic, and links.
function parseInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const regex = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(_[^_]+_)|(\[[^\]]+\]\([^)\s]+\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${i}`;
    if (token.startsWith("`")) {
      nodes.push(<code key={key} style={codeStyle}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("*")) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith("_")) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith("[")) {
      const m = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(token);
      if (m) nodes.push(<a key={key} href={m[2]} target="_blank" rel="noreferrer" style={linkStyle}>{m[1]}</a>);
    }
    lastIndex = regex.lastIndex;
    i++;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

const HEADING = /^(#{1,3})\s+(.*)$/;
const BULLET = /^\s*[-*]\s+/;
const NUMBERED = /^\s*\d+\.\s+/;
// A GFM table needs a row of cells followed by a separator like |---|:--:|.
const TABLE_ROW = /\|/;
const TABLE_SEP = /^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/;

function tableCells(line: string): string[] {
  return line.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim());
}

const tdStyle: React.CSSProperties = { border: "1px solid var(--border-subtle)", padding: "5px 9px", textAlign: "left", verticalAlign: "top" };

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const heading = HEADING.exec(line);
    if (heading) {
      const level = heading[1].length;
      const fontSize = level === 1 ? "var(--text-lg)" : level === 2 ? "var(--text-md)" : "var(--text-base)";
      blocks.push(
        <div key={key++} style={{ fontWeight: 700, fontSize, color: "var(--text-strong)", margin: blocks.length ? "10px 0 4px" : "0 0 4px" }}>
          {parseInline(heading[2], `h${key}`)}
        </div>,
      );
      i++;
      continue;
    }

    // Table: a header row, a separator row, then zero or more body rows.
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
      const header = tableCells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim() && TABLE_ROW.test(lines[i])) {
        rows.push(tableCells(lines[i]));
        i++;
      }
      blocks.push(
        <div key={key++} style={{ overflowX: "auto", margin: "8px 0" }}>
          <table style={{ borderCollapse: "collapse", fontSize: "0.95em", width: "100%" }}>
            <thead>
              <tr>{header.map((c, idx) => <th key={idx} style={{ ...tdStyle, fontWeight: 700, background: "var(--surface-sunken)" }}>{parseInline(c, `th${key}-${idx}`)}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((cells, ri) => (
                <tr key={ri}>{header.map((_, ci) => <td key={ci} style={tdStyle}>{parseInline(cells[ci] ?? "", `td${key}-${ri}-${ci}`)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (BULLET.test(line)) {
      const items: string[] = [];
      while (i < lines.length && BULLET.test(lines[i])) { items.push(lines[i].replace(BULLET, "")); i++; }
      blocks.push(
        <ul key={key++} style={{ margin: "6px 0", paddingLeft: 22, display: "grid", gap: 3 }}>
          {items.map((it, idx) => <li key={idx}>{parseInline(it, `ul${key}-${idx}`)}</li>)}
        </ul>,
      );
      continue;
    }

    if (NUMBERED.test(line)) {
      const items: string[] = [];
      while (i < lines.length && NUMBERED.test(lines[i])) { items.push(lines[i].replace(NUMBERED, "")); i++; }
      blocks.push(
        <ol key={key++} style={{ margin: "6px 0", paddingLeft: 22, display: "grid", gap: 3 }}>
          {items.map((it, idx) => <li key={idx}>{parseInline(it, `ol${key}-${idx}`)}</li>)}
        </ol>,
      );
      continue;
    }

    // Paragraph: gather consecutive plain lines, preserving single line breaks.
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !HEADING.test(lines[i]) && !BULLET.test(lines[i]) && !NUMBERED.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++} style={{ margin: blocks.length ? "6px 0 0" : 0 }}>
        {para.map((l, idx) => (
          <React.Fragment key={idx}>
            {idx > 0 ? <br /> : null}
            {parseInline(l, `p${key}-${idx}`)}
          </React.Fragment>
        ))}
      </p>,
    );
  }

  return <>{blocks}</>;
}
