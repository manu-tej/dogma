"use strict";

const { parseCsv } = require("./domainValidators");
const { extractWorkflowGraphs, flattenWorkflowCalls, flattenWorkflowProcesses } = require("./workflowGraph");

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function countDataLines(text, skipPrefix = "#") {
  return text.split(/\r?\n/).filter((line) => line.trim() && !line.startsWith(skipPrefix)).length;
}

function firstFile(fileMap, predicate) {
  return Object.keys(fileMap).find(predicate);
}

function extractWorkspaceContext(fileMap) {
  const sampleFile = firstFile(fileMap, (file) => /(^|\/)(sample_sheet|samples)\.csv$/i.test(file));
  const metadataFile = firstFile(fileMap, (file) => /(^|\/)(metadata|project)\.json$/i.test(file));
  const workflowFiles = Object.keys(fileMap).filter((file) => file.toLowerCase().endsWith(".nf") || file.toLowerCase().endsWith("nextflow.config"));
  const bedFiles = Object.keys(fileMap).filter((file) => file.toLowerCase().endsWith(".bed"));
  const vcfFiles = Object.keys(fileMap).filter((file) => file.toLowerCase().endsWith(".vcf"));
  const annotationFiles = Object.keys(fileMap).filter((file) => /\.(gtf|gff|gff3)$/i.test(file));
  const fastqFiles = Object.keys(fileMap).filter((file) => /\.(fastq|fq)$/i.test(file));

  const context = {
    sampleFile,
    metadataFile,
    workflowFiles,
    bedFiles,
    vcfFiles,
    annotationFiles,
    fastqFiles,
    samples: {
      count: 0,
      conditions: [],
      strandedness: []
    },
    reference: {},
    privacy: {},
    counts: {
      intervals: 0,
      variants: 0,
      annotations: 0,
      fastqReads: 0
    },
    workflowGraphs: [],
    workflowProcesses: [],
    workflowCalls: []
  };

  if (sampleFile) {
    const parsed = parseCsv(fileMap[sampleFile]);
    const conditions = new Set();
    const strandedness = new Set();
    for (const record of parsed.records) {
      if (record.data.condition) conditions.add(record.data.condition);
      if (record.data.strandedness) strandedness.add(record.data.strandedness);
    }
    context.samples.count = parsed.records.length;
    context.samples.conditions = [...conditions].sort();
    context.samples.strandedness = [...strandedness].sort();
  }

  if (metadataFile) {
    const metadata = safeJson(fileMap[metadataFile]);
    if (metadata) {
      context.assay = metadata.assay;
      context.organism = metadata.organism;
      context.reference = metadata.reference || {};
      context.privacy = metadata.privacy || {};
    }
  }

  context.counts.intervals = bedFiles.reduce((total, file) => total + countDataLines(fileMap[file]), 0);
  context.counts.variants = vcfFiles.reduce((total, file) => total + countDataLines(fileMap[file]), 0);
  context.counts.annotations = annotationFiles.reduce((total, file) => total + countDataLines(fileMap[file]), 0);
  context.counts.fastqReads = fastqFiles.reduce((total, file) => total + Math.floor(fileMap[file].split(/\r?\n/).filter(Boolean).length / 4), 0);
  context.workflowGraphs = extractWorkflowGraphs(fileMap);
  context.workflowProcesses = flattenWorkflowProcesses(context.workflowGraphs);
  context.workflowCalls = flattenWorkflowCalls(context.workflowGraphs);

  return context;
}

function listOrNone(items) {
  return items && items.length ? items.join(", ") : "not detected";
}

function renderContextReport(context, issues) {
  const errors = issues.filter((item) => item.severity === "error").length;
  const warnings = issues.filter((item) => item.severity === "warning").length;
  const issueRows = issues.length
    ? issues.map((item) => `| ${item.severity} | ${item.file}:${item.line} | ${item.message.replace(/\|/g, "\\|")} |`).join("\n")
    : "| pass | workspace | No Dogma domain issues detected. |";

  return [
    "# Dogma Context Report",
    "",
    "## Workspace",
    "",
    `- Scan source: ${context.scanSource || "extension"}`,
    `- Assay: ${context.assay || "not detected"}`,
    `- Organism: ${context.organism || "not detected"}`,
    `- Sample sheet: ${context.sampleFile || "not detected"}`,
    `- Samples: ${context.samples.count}`,
    `- Conditions: ${listOrNone(context.samples.conditions)}`,
    `- Strandedness: ${listOrNone(context.samples.strandedness)}`,
    `- Genome build: ${context.reference.genome_build || "not detected"}`,
    `- Annotation: ${context.reference.annotation || "not detected"}`,
    `- Human data: ${String(context.privacy.contains_human_data ?? "not declared")}`,
    "",
    "## Files",
    "",
    `- Workflow files: ${listOrNone(context.workflowFiles)}`,
    `- Workflow processes: ${listOrNone(context.workflowProcesses)}`,
    `- Workflow calls: ${listOrNone(context.workflowCalls)}`,
    `- BED files: ${listOrNone(context.bedFiles)} (${context.counts.intervals} interval rows)`,
    `- VCF files: ${listOrNone(context.vcfFiles)} (${context.counts.variants} variant rows)`,
    `- Annotation files: ${listOrNone(context.annotationFiles)} (${context.counts.annotations} feature rows)`,
    `- FASTQ files: ${listOrNone(context.fastqFiles)} (${context.counts.fastqReads} read records)`,
    `- Metadata file: ${context.metadataFile || "not detected"}`,
    "",
    "## Findings",
    "",
    `- Errors: ${errors}`,
    `- Warnings: ${warnings}`,
    "",
    "| Severity | Location | Message |",
    "| --- | --- | --- |",
    issueRows,
    "",
    "## Workflow Graph",
    "",
    "| File | Processes | Calls | Edges |",
    "| --- | --- | --- | --- |",
    ...(context.workflowGraphs.length
      ? context.workflowGraphs.map((graph) => {
          const processes = graph.processes.map((process) => `${process.name}:${process.line}`).join(", ") || "none";
          const calls = graph.calls.map((call) => `${call.process}:${call.line}`).join(", ") || "none";
          const edges = graph.edges.map((edge) => `${edge.from}->${edge.to}`).join(", ") || "none";
          return `| ${graph.file} | ${processes} | ${calls} | ${edges} |`;
        })
      : ["| not detected | none | none | none |"]),
    "",
    "## Suggested Next Actions",
    "",
    "- Fix error-level findings before real workflow execution.",
    "- Use synthetic fixtures for regression tests.",
    "- Record genome build, annotation release, strandedness, tool versions, and reference checksums.",
    "- Use Dogma quick fixes only for narrow workflow-safe edits.",
    ""
  ].join("\n");
}

function renderContextHtml(context, issues, escapeHtml) {
  const rows = [
    ["Scan source", context.scanSource || "extension"],
    ["Assay", context.assay || "not detected"],
    ["Organism", context.organism || "not detected"],
    ["Sample sheet", context.sampleFile || "not detected"],
    ["Samples", String(context.samples.count)],
    ["Conditions", listOrNone(context.samples.conditions)],
    ["Strandedness", listOrNone(context.samples.strandedness)],
    ["Genome build", context.reference.genome_build || "not detected"],
    ["Annotation", context.reference.annotation || "not detected"],
    ["Workflow files", listOrNone(context.workflowFiles)],
    ["Workflow processes", listOrNone(context.workflowProcesses)],
    ["Workflow calls", listOrNone(context.workflowCalls)],
    ["BED intervals", String(context.counts.intervals)],
    ["VCF variants", String(context.counts.variants)],
    ["FASTQ reads", String(context.counts.fastqReads || 0)]
  ];

  const tableRows = rows
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");

  const errors = issues.filter((item) => item.severity === "error").length;
  const warnings = issues.filter((item) => item.severity === "warning").length;

  return `<section>
    <h2>Workspace Context</h2>
    <table>${tableRows}</table>
    <p><strong>${issues.length}</strong> finding(s): ${errors} error(s), ${warnings} warning(s).</p>
  </section>`;
}

module.exports = {
  extractWorkspaceContext,
  renderContextHtml,
  renderContextReport
};
