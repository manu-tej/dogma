"use strict";

function nodeId(name, index) {
  const cleaned = String(name || "node")
    .replace(/[^A-Za-z0-9_]/g, "_")
    .replace(/^([^A-Za-z_])/, "_$1");
  return `${cleaned || "node"}_${index}`;
}

function escapeMermaidLabel(value) {
  return String(value || "").replace(/"/g, "'");
}

function renderMermaidForGraph(graph) {
  const processIds = new Map();
  const lines = ["flowchart LR"];

  graph.processes.forEach((process, index) => {
    const id = nodeId(process.name, index + 1);
    processIds.set(process.name, id);
    lines.push(`  ${id}["${escapeMermaidLabel(process.name)}<br/>${escapeMermaidLabel(graph.file)}:${process.line}"]`);
  });

  graph.edges.forEach((edge) => {
    const from = processIds.get(edge.from);
    const to = processIds.get(edge.to);
    if (from && to) {
      lines.push(`  ${from} --> ${to}`);
    }
  });

  if (lines.length === 1) {
    lines.push('  none["No workflow processes detected"]');
  }

  return lines.join("\n");
}

function tableRows(items, render) {
  return items.length ? items.map(render) : ["| none | none | none |"];
}

function renderWorkflowGraphReport(graphs) {
  const detected = graphs || [];
  const sections = detected.length
    ? detected.map((graph) => {
        const processRows = tableRows(graph.processes || [], (process) => `| ${process.name} | ${graph.file} | ${process.line} |`);
        const channelRows = tableRows(graph.channels || [], (channel) => `| ${channel.name} | ${graph.file} | ${channel.line} |`);
        const callRows = tableRows(graph.calls || [], (call) => `| ${call.process} | ${graph.file} | ${call.line} |`);
        const edgeRows = (graph.edges || []).length
          ? graph.edges.map((edge) => `| ${edge.from} | ${edge.to} | inferred call order |`)
          : ["| none | none | no inferred edges |"];

        return [
          `## ${graph.file}`,
          "",
          "```mermaid",
          renderMermaidForGraph(graph),
          "```",
          "",
          "### Processes",
          "",
          "| Process | File | Line |",
          "| --- | --- | --- |",
          ...processRows,
          "",
          "### Channels",
          "",
          "| Channel | File | Line |",
          "| --- | --- | --- |",
          ...channelRows,
          "",
          "### Calls",
          "",
          "| Process | File | Line |",
          "| --- | --- | --- |",
          ...callRows,
          "",
          "### Edges",
          "",
          "| From | To | Evidence |",
          "| --- | --- | --- |",
          ...edgeRows,
          ""
        ].join("\n");
      }).join("\n")
    : [
        "No Nextflow workflow graph was detected in the current workspace scan.",
        "",
        "Run a scan after adding `*.nf` workflow files, or use the local service for broader workflow indexing.",
        ""
      ].join("\n");

  return [
    "# Dogma Workflow Graph",
    "",
    "This report is derived from parsed workflow source. Edges are conservative hints inferred from process call order and should be reviewed before changing execution logic.",
    "",
    sections
  ].join("\n");
}

module.exports = {
  renderMermaidForGraph,
  renderWorkflowGraphReport
};
