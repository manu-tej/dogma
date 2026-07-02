"use strict";

const SEVERITY = {
  error: 0,
  warning: 1,
  info: 2
};

function lineRange(text, oneBasedLine) {
  const lines = text.split(/\r?\n/);
  const lineIndex = Math.max(0, Math.min((oneBasedLine || 1) - 1, Math.max(lines.length - 1, 0)));
  const lineText = lines[lineIndex] || "";
  return {
    startLine: lineIndex,
    startCharacter: 0,
    endLine: lineIndex,
    endCharacter: Math.max(lineText.length, 1)
  };
}

function diagnosticEntries(fileMap, issues) {
  const byFile = new Map();

  for (const item of issues) {
    const text = fileMap[item.file] || "";
    const entry = {
      file: item.file,
      severity: SEVERITY[item.severity] ?? SEVERITY.info,
      message: item.message,
      code: item.code,
      source: "Dogma",
      range: lineRange(text, item.line)
    };

    if (!byFile.has(item.file)) {
      byFile.set(item.file, []);
    }
    byFile.get(item.file).push(entry);
  }

  return byFile;
}

function isCandidatePath(path) {
  const normalized = path.toLowerCase().replace(/\\/g, "/");
  return (
    normalized.endsWith("sample_sheet.csv") ||
    normalized.endsWith("sample_sheet.csv.gz") ||
    normalized.endsWith("samples.csv") ||
    normalized.endsWith("samples.csv.gz") ||
    normalized.endsWith(".bed") ||
    normalized.endsWith(".bed.gz") ||
    normalized.endsWith(".vcf") ||
    normalized.endsWith(".vcf.gz") ||
    normalized.endsWith(".gtf") ||
    normalized.endsWith(".gtf.gz") ||
    normalized.endsWith(".gff") ||
    normalized.endsWith(".gff.gz") ||
    normalized.endsWith(".gff3") ||
    normalized.endsWith(".gff3.gz") ||
    normalized.endsWith(".fastq") ||
    normalized.endsWith(".fq") ||
    normalized.endsWith(".fastq.gz") ||
    normalized.endsWith(".fq.gz") ||
    normalized.endsWith("metadata.json") ||
    normalized.endsWith("project.json") ||
    normalized.endsWith(".nf") ||
    normalized.endsWith("nextflow.config") ||
    normalized.endsWith("snakefile") ||
    normalized.endsWith(".smk") ||
    normalized.endsWith(".snakefile") ||
    normalized.endsWith(".fai") ||
    normalized.endsWith("multiqc_general_stats.txt")
  );
}

module.exports = {
  diagnosticEntries,
  isCandidatePath,
  lineRange,
  SEVERITY
};
