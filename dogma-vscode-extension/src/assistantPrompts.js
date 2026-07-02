"use strict";

function issueSummary(issues) {
  if (!issues.length) return "No Dogma domain findings are currently reported.";
  return issues.map((item) => `- ${item.severity}: ${item.file}:${item.line} ${item.message}`).join("\n");
}

function buildAssistantPrompt(context, issues) {
  return [
    "You are Dogma, an AI bioinformatics IDE assistant.",
    "",
    "Use the parsed workspace context and current findings below. Do not invent sample metadata, reference builds, annotations, clinical interpretations, or file contents. Prefer small workflow-safe patches and synthetic test fixtures.",
    "",
    "## Workspace Context",
    "",
    `- Assay: ${context.assay || "not detected"}`,
    `- Organism: ${context.organism || "not detected"}`,
    `- Sample sheet: ${context.sampleFile || "not detected"}`,
    `- Sample count: ${context.samples.count}`,
    `- Conditions: ${context.samples.conditions.length ? context.samples.conditions.join(", ") : "not detected"}`,
    `- Strandedness: ${context.samples.strandedness.length ? context.samples.strandedness.join(", ") : "not detected"}`,
    `- Genome build: ${context.reference.genome_build || "not detected"}`,
    `- Annotation: ${context.reference.annotation || "not detected"}`,
    `- Workflow files: ${context.workflowFiles.length ? context.workflowFiles.join(", ") : "not detected"}`,
    `- Workflow processes: ${context.workflowProcesses.length ? context.workflowProcesses.join(", ") : "not detected"}`,
    `- Workflow calls: ${context.workflowCalls.length ? context.workflowCalls.join(", ") : "not detected"}`,
    `- BED files: ${context.bedFiles.length ? context.bedFiles.join(", ") : "not detected"} (${context.counts.intervals} interval rows)`,
    `- VCF files: ${context.vcfFiles.length ? context.vcfFiles.join(", ") : "not detected"} (${context.counts.variants} variant rows)`,
    `- Annotation files: ${context.annotationFiles?.length ? context.annotationFiles.join(", ") : "not detected"} (${context.counts.annotations || 0} feature rows)`,
    `- FASTQ files: ${context.fastqFiles?.length ? context.fastqFiles.join(", ") : "not detected"} (${context.counts.fastqReads || 0} read records)`,
    `- Human data flag: ${String(context.privacy.contains_human_data ?? "not declared")}`,
    "",
    "## Current Findings",
    "",
    issueSummary(issues),
    "",
    "## Requested Response",
    "",
    "1. Identify the highest-risk bioinformatics problems first.",
    "2. Explain the evidence from files and parsed context.",
    "3. Propose the smallest safe fix.",
    "4. Suggest synthetic regression tests.",
    "5. List any missing assumptions that must be clarified before real analysis."
  ].join("\n");
}

function buildSyntheticTestPlan(context, issues) {
  const hasSampleIssues = issues.some((item) => item.file.endsWith(".csv"));
  const hasVcfIssues = issues.some((item) => item.file.endsWith(".vcf"));
  const hasBedIssues = issues.some((item) => item.file.endsWith(".bed"));
  const items = [
    "Create a minimal sample sheet with two control and two treatment samples.",
    "Use tiny synthetic paired FASTQ fixtures or stub paths for workflow dry runs.",
    "Assert sample_id uniqueness and required FASTQ columns before tuple creation.",
    "Record genome build, annotation release, strandedness, and tool versions in provenance output."
  ];

  if (hasSampleIssues) {
    items.push("Add negative sample sheet fixtures for duplicate sample IDs and missing FASTQ pairs.");
  }
  if (hasBedIssues) {
    items.push("Add BED coordinate fixtures for zero-length intervals, negative starts, and chr versus bare contig names.");
  }
  if (hasVcfIssues) {
    items.push("Add VCF fixtures covering missing reference headers, non-PASS FILTER values, low depth, and invalid 1-based POS.");
  }
  if (issues.some((item) => /\.(fastq|fq)$/i.test(item.file))) {
    items.push("Add FASTQ fixtures for malformed headers, incomplete records, invalid bases, and sequence/quality length mismatches.");
  }
  if (context.privacy.contains_human_data === true) {
    items.push("Use only synthetic or public miniature data in tests; do not include private human sample metadata.");
  }

  return ["# Dogma Synthetic Test Plan", "", ...items.map((item) => `- ${item}`), ""].join("\n");
}

module.exports = {
  buildAssistantPrompt,
  buildSyntheticTestPlan,
  issueSummary
};
