"use strict";

const { parseCsv } = require("./domainValidators");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

function table(headers, rows) {
  const head = headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("");
  const body = rows
    .slice(0, 200)
    .map((row) => `<tr>${headers.map((header) => `<td>${escapeHtml(row[header] ?? "")}</td>`).join("")}</tr>`)
    .join("");

  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function previewCsv(file, text) {
  const parsed = parseCsv(text);
  const rows = parsed.records.map((record) => record.data);
  return {
    title: `Sample sheet preview: ${file}`,
    summary: `${rows.length} row(s), ${parsed.headers.length} column(s)`,
    html: table(parsed.headers, rows)
  };
}

function previewBed(file, text) {
  const rows = text
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.startsWith("#"))
    .map((line) => {
      const [chrom, start, end, name = "", score = "", strand = ""] = line.split(/\t/);
      return { chrom, start, end, name, score, strand };
    });

  return {
    title: `BED preview: ${file}`,
    summary: `${rows.length} interval row(s). BED coordinates are 0-based half-open.`,
    html: table(["chrom", "start", "end", "name", "score", "strand"], rows)
  };
}

function parseInfo(infoText) {
  return Object.fromEntries(
    infoText
      .split(";")
      .filter(Boolean)
      .map((entry) => {
        const [key, value = "true"] = entry.split("=");
        return [key, value];
      })
  );
}

function previewVcf(file, text) {
  const rows = text
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.startsWith("#"))
    .map((line) => {
      const [chrom, pos, id, ref, alt, qual, filter, infoText = ""] = line.split(/\t/);
      const info = parseInfo(infoText);
      return {
        chrom,
        pos,
        id,
        ref,
        alt,
        qual,
        filter,
        depth: info.DP || "",
        allele_fraction: info.AF || ""
      };
    });

  return {
    title: `VCF preview: ${file}`,
    summary: `${rows.length} variant row(s). VCF POS is 1-based.`,
    html: table(["chrom", "pos", "id", "ref", "alt", "qual", "filter", "depth", "allele_fraction"], rows)
  };
}

function previewGtfGff(file, text) {
  const rows = text
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.startsWith("#"))
    .map((line) => {
      const [seqid, source, type, start, end, score, strand, phase, attributes = ""] = line.split(/\t/);
      return { seqid, source, type, start, end, score, strand, phase, attributes };
    });

  return {
    title: `Annotation preview: ${file}`,
    summary: `${rows.length} annotation feature row(s). GTF/GFF coordinates are 1-based closed.`,
    html: table(["seqid", "source", "type", "start", "end", "score", "strand", "phase", "attributes"], rows)
  };
}

function previewFastq(file, text) {
  const lines = text.split(/\r?\n/);
  if (lines.length && lines[lines.length - 1] === "") {
    lines.pop();
  }
  const rows = [];
  let totalBases = 0;
  for (let offset = 0; offset + 3 < lines.length && rows.length < 200; offset += 4) {
    const header = lines[offset] || "";
    const sequence = lines[offset + 1] || "";
    const quality = lines[offset + 3] || "";
    totalBases += sequence.length;
    rows.push({
      read: header.replace(/^@/, ""),
      length: sequence.length,
      gc_percent: sequence.length ? Math.round(((sequence.match(/[GCgc]/g) || []).length / sequence.length) * 1000) / 10 : "",
      quality_length: quality.length
    });
  }

  const records = Math.floor(lines.length / 4);
  return {
    title: `FASTQ preview: ${file}`,
    summary: `${records} read record(s), ${totalBases} observed base(s) in preview. FASTQ uses four lines per read.`,
    html: table(["read", "length", "gc_percent", "quality_length"], rows)
  };
}

function flattenJson(value, prefix = "") {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return [{ key: prefix || "value", value: Array.isArray(value) ? value.join(", ") : String(value) }];
  }

  return Object.entries(value).flatMap(([key, child]) => flattenJson(child, prefix ? `${prefix}.${key}` : key));
}

function previewJson(file, text) {
  const parsed = JSON.parse(text);
  const rows = flattenJson(parsed);
  return {
    title: `Metadata preview: ${file}`,
    summary: `${rows.length} metadata field(s)`,
    html: table(["key", "value"], rows)
  };
}

function previewPlain(file, text) {
  return {
    title: `Text preview: ${file}`,
    summary: `${text.split(/\r?\n/).length} line(s)`,
    html: `<pre>${escapeHtml(text.slice(0, 20000))}</pre>`
  };
}

function buildPreview(file, text) {
  const lower = file.toLowerCase();
  if (lower.endsWith(".csv")) return previewCsv(file, text);
  if (lower.endsWith(".bed")) return previewBed(file, text);
  if (lower.endsWith(".vcf")) return previewVcf(file, text);
  if (lower.endsWith(".gtf") || lower.endsWith(".gff") || lower.endsWith(".gff3")) return previewGtfGff(file, text);
  if (lower.endsWith(".fastq") || lower.endsWith(".fq")) return previewFastq(file, text);
  if (lower.endsWith(".json")) return previewJson(file, text);
  return previewPlain(file, text);
}

function renderPreviewHtml(file, text) {
  let preview;
  try {
    preview = buildPreview(file, text);
  } catch (error) {
    preview = {
      title: `Preview error: ${file}`,
      summary: error.message,
      html: `<pre>${escapeHtml(text.slice(0, 20000))}</pre>`
    };
  }

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; }
    h1 { font-size: 18px; margin-top: 0; }
    p { color: var(--vscode-descriptionForeground); }
    table { border-collapse: collapse; width: 100%; font-family: var(--vscode-editor-font-family); font-size: var(--vscode-editor-font-size); }
    th, td { border: 1px solid var(--vscode-panel-border); padding: 6px 8px; text-align: left; vertical-align: top; white-space: nowrap; }
    th { position: sticky; top: 0; background: var(--vscode-editor-background); }
    pre { white-space: pre-wrap; font-family: var(--vscode-editor-font-family); }
  </style>
</head>
<body>
  <h1>${escapeHtml(preview.title)}</h1>
  <p>${escapeHtml(preview.summary)}</p>
  ${preview.html}
</body>
</html>`;
}

module.exports = {
  buildPreview,
  previewFastq,
  previewGtfGff,
  renderPreviewHtml
};
