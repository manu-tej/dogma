"use strict";

function shellQuote(value) {
  if (/^[A-Za-z0-9_./:=+-]+$/.test(value)) return value;
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function hasErrorIssues(issues) {
  return issues.some((item) => item.severity === "error");
}

function buildNextflowCommands(context) {
  return context.workflowFiles
    .filter((file) => file.toLowerCase().endsWith(".nf"))
    .map((file) => ({
      label: `Nextflow stub run for ${file}`,
      command: `nextflow run ${shellQuote(file)} -stub-run`,
      purpose: "Compile the workflow graph and execute process stubs without running real tools."
    }));
}

function buildSafeRunPlan(context, issues) {
  const commands = buildNextflowCommands(context);
  const blocked = hasErrorIssues(issues);
  const errorCount = issues.filter((item) => item.severity === "error").length;
  const warningCount = issues.filter((item) => item.severity === "warning").length;

  return {
    blocked,
    commands,
    errorCount,
    warningCount,
    notes: [
      "Review commands before running them.",
      "Run scans and fix error-level findings before real analysis.",
      "Prefer stub or test profiles before touching full datasets.",
      "Capture tool versions, parameters, reference files, and checksums in provenance output."
    ]
  };
}

function renderRunPlan(context, issues) {
  const plan = buildSafeRunPlan(context, issues);
  const commandRows = plan.commands.length
    ? plan.commands.map((item) => `| ${item.label} | \`${item.command}\` | ${item.purpose} |`).join("\n")
    : "| none | not available | No Nextflow workflow files were detected. |";
  const issueRows = issues.length
    ? issues.map((item) => `| ${item.severity} | ${item.file}:${item.line} | ${item.message.replace(/\|/g, "\\|")} |`).join("\n")
    : "| pass | workspace | No Dogma findings. |";

  return [
    "# Dogma Safe Run Plan",
    "",
    `Status: ${plan.blocked ? "blocked until error-level findings are fixed" : "ready for cautious dry-run/stub-run review"}`,
    "",
    "## Detected Context",
    "",
    `- Workflow files: ${context.workflowFiles.length ? context.workflowFiles.join(", ") : "not detected"}`,
    `- Workflow processes: ${context.workflowProcesses.length ? context.workflowProcesses.join(", ") : "not detected"}`,
    `- Sample sheet: ${context.sampleFile || "not detected"}`,
    `- Samples: ${context.samples.count}`,
    `- Genome build: ${context.reference.genome_build || "not detected"}`,
    `- Annotation: ${context.reference.annotation || "not detected"}`,
    "",
    "## Manual Commands",
    "",
    "| Step | Command | Purpose |",
    "| --- | --- | --- |",
    commandRows,
    "",
    "## Current Findings",
    "",
    `- Errors: ${plan.errorCount}`,
    `- Warnings: ${plan.warningCount}`,
    "",
    "| Severity | Location | Message |",
    "| --- | --- | --- |",
    issueRows,
    "",
    "## Safety Notes",
    "",
    ...plan.notes.map((note) => `- ${note}`),
    ""
  ].join("\n");
}

module.exports = {
  buildSafeRunPlan,
  renderRunPlan
};
