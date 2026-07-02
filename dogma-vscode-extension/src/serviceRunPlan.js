"use strict";

function listRows(items) {
  return items && items.length ? items.map((item) => `- ${item}`).join("\n") : "- none";
}

function renderServiceRunPlan(plan) {
  const commandRows = plan.commands && plan.commands.length
    ? plan.commands.map((command) => {
        const blocked = command.blocked_reason || "none";
        return `| ${command.id} | ${command.engine} | ${command.mode} | \`${command.command}\` | ${String(command.execution_allowed)} | ${blocked} |`;
      }).join("\n")
    : "| none | none | none | not available | false | No workflow dry-run or stub-run command was generated. |";

  return [
    "# Dogma Local Service Run Plan",
    "",
    `Status: ${plan.status || "unknown"}`,
    `Root: ${plan.root || "not reported"}`,
    `Execution allowed: ${String(Boolean(plan.execution_allowed))}`,
    `Errors: ${plan.error_count || 0}`,
    `Warnings: ${plan.warning_count || 0}`,
    "",
    "## Commands",
    "",
    "| ID | Engine | Mode | Command | Execution Allowed | Blocked Reason |",
    "| --- | --- | --- | --- | --- | --- |",
    commandRows,
    "",
    "## Safety Notes",
    "",
    listRows(plan.safety_notes || []),
    "",
    "## Provenance Expectations",
    "",
    listRows(plan.provenance || []),
    ""
  ].join("\n");
}

function renderExecutionResult(result) {
  const command = result.command || {};
  return [
    "# Dogma Local Service Execution Result",
    "",
    `Status: ${result.status || "unknown"}`,
    `Executed: ${String(Boolean(result.executed))}`,
    `Command: ${command.command ? `\`${command.command}\`` : "not selected"}`,
    `Message: ${result.message || "none"}`,
    `Return code: ${result.return_code ?? "not available"}`,
    "",
    "## Stdout",
    "",
    "```text",
    result.stdout || "",
    "```",
    "",
    "## Stderr",
    "",
    "```text",
    result.stderr || "",
    "```",
    ""
  ].join("\n");
}

module.exports = {
  renderExecutionResult,
  renderServiceRunPlan
};
