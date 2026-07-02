"use strict";

function lineNumberAt(text, index) {
  return text.slice(0, index).split(/\r?\n/).length;
}

function extractNextflowGraph(file, text) {
  const processes = [];
  const processRegex = /(?:^|\n)\s*process\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{/g;
  let match;

  while ((match = processRegex.exec(text))) {
    const bodyStart = processRegex.lastIndex;
    const closeIndex = text.indexOf("\n}", bodyStart);
    const body = closeIndex >= 0 ? text.slice(bodyStart, closeIndex) : text.slice(bodyStart);
    const containerMatch = body.match(/(?:^|\n)\s*container\s+['"]?([^'"\n]+)/);
    processes.push({
      file,
      name: match[1],
      line: lineNumberAt(text, match.index + match[0].indexOf("process")),
      container: containerMatch ? containerMatch[1].trim() : undefined
    });
  }

  const channels = [];
  const channelRegex = /\.set\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}/g;
  while ((match = channelRegex.exec(text))) {
    channels.push({
      file,
      name: match[1],
      line: lineNumberAt(text, match.index)
    });
  }

  const calls = [];
  for (const process of processes) {
    const callRegex = new RegExp(`(^|[^A-Za-z0-9_])${process.name}\\s*\\(`, "g");
    while ((match = callRegex.exec(text))) {
      const prefix = match[1] || "";
      const callIndex = match.index + prefix.length;
      const before = text.slice(Math.max(0, callIndex - 16), callIndex);
      if (/process\s+$/.test(before)) continue;
      calls.push({
        file,
        process: process.name,
        line: lineNumberAt(text, callIndex)
      });
    }
  }

  calls.sort((a, b) => a.line - b.line || a.process.localeCompare(b.process));

  const edges = [];
  for (let index = 1; index < calls.length; index += 1) {
    edges.push({
      from: calls[index - 1].process,
      to: calls[index].process
    });
  }

  return { file, processes, channels, calls, edges };
}

function extractWorkflowGraphs(fileMap) {
  return Object.entries(fileMap)
    .filter(([file]) => file.toLowerCase().endsWith(".nf"))
    .map(([file, text]) => extractNextflowGraph(file, text));
}

function flattenWorkflowProcesses(graphs) {
  return graphs.flatMap((graph) => graph.processes.map((process) => `${process.name} (${graph.file}:${process.line})`));
}

function flattenWorkflowCalls(graphs) {
  return graphs.flatMap((graph) => graph.calls.map((call) => `${call.process} (${graph.file}:${call.line})`));
}

module.exports = {
  extractNextflowGraph,
  extractWorkflowGraphs,
  flattenWorkflowCalls,
  flattenWorkflowProcesses
};
