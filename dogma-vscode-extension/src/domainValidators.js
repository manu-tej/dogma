"use strict";

const SAMPLE_SHEET_COLUMNS = ["sample_id", "condition", "replicate", "fastq_1", "fastq_2", "strandedness"];

function issue(severity, file, line, message) {
  return { severity, file, line, message };
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return { headers: [], records: [] };

  const headers = lines[0].split(",").map((header) => header.trim());
  const records = lines.slice(1).map((line, offset) => {
    const values = line.split(",");
    return {
      line: offset + 2,
      data: Object.fromEntries(headers.map((header, index) => [header, (values[index] || "").trim()]))
    };
  });

  return { headers, records };
}

function validateSampleSheet(file, text) {
  const { headers, records } = parseCsv(text);
  const issues = [];
  const missing = SAMPLE_SHEET_COLUMNS.filter((column) => !headers.includes(column));

  if (missing.length > 0) {
    issues.push(issue("error", file, 1, `Missing required sample sheet columns: ${missing.join(", ")}`));
  }

  const seen = new Map();
  const strandednessValues = new Set();

  for (const record of records) {
    const sampleId = record.data.sample_id;
    if (sampleId) {
      if (seen.has(sampleId)) {
        issues.push(issue("error", file, record.line, `Duplicate sample_id '${sampleId}'.`));
      }
      seen.set(sampleId, record.line);
    }

    if (!record.data.fastq_1 || !record.data.fastq_2) {
      issues.push(issue("error", file, record.line, "Paired-end sample rows require fastq_1 and fastq_2."));
    }

    if (record.data.strandedness) {
      strandednessValues.add(record.data.strandedness);
    }
  }

  if (strandednessValues.size > 1) {
    issues.push(issue("warning", file, 1, "Mixed strandedness values require explicit per-sample workflow handling."));
  }

  return issues;
}

function validateBed(file, text) {
  const issues = [];
  const styles = new Set();

  text.split(/\r?\n/).forEach((line, index) => {
    if (!line.trim() || line.startsWith("#")) return;

    const fields = line.split(/\t/);
    const lineNumber = index + 1;
    if (fields.length < 3) {
      issues.push(issue("error", file, lineNumber, "BED row needs at least chrom, start, and end."));
      return;
    }

    const [chrom, startText, endText] = fields;
    const start = Number(startText);
    const end = Number(endText);
    styles.add(chrom.startsWith("chr") ? "chr" : "bare");

    if (!Number.isInteger(start) || !Number.isInteger(end)) {
      issues.push(issue("error", file, lineNumber, "BED start and end must be integer coordinates."));
    } else if (start < 0 || end <= start) {
      issues.push(issue("error", file, lineNumber, "BED uses 0-based half-open coordinates; require 0 <= start < end."));
    }
  });

  if (styles.size > 1) {
    issues.push(issue("warning", file, 1, "Mixed chromosome naming styles can break joins with BAM/VCF files."));
  }

  return issues;
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

function validateVcf(file, text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  const issues = [];
  const hasFileFormat = lines.some((line) => line.startsWith("##fileformat=VCF"));
  const hasReference = lines.some((line) => line.startsWith("##reference="));
  const hasHeader = lines.some((line) => line.startsWith("#CHROM"));

  if (!hasFileFormat) issues.push(issue("error", file, 1, "VCF is missing ##fileformat header."));
  if (!hasReference) issues.push(issue("warning", file, 1, "VCF should declare ##reference."));
  if (!hasHeader) issues.push(issue("error", file, 1, "VCF is missing #CHROM header."));

  lines.forEach((line, index) => {
    if (line.startsWith("#")) return;

    const lineNumber = index + 1;
    const fields = line.split(/\t/);
    if (fields.length < 8) {
      issues.push(issue("error", file, lineNumber, "VCF record needs at least 8 columns."));
      return;
    }

    const [, posText, id, ref, alt, , filter, infoText] = fields;
    const pos = Number(posText);
    const info = parseInfo(infoText);
    const depth = Number(info.DP || 0);

    if (!Number.isInteger(pos) || pos < 1) {
      issues.push(issue("error", file, lineNumber, "VCF POS must be 1-based positive integer."));
    }
    if (!ref || !alt || alt === ".") {
      issues.push(issue("error", file, lineNumber, `${id || "variant"} is missing REF or ALT.`));
    }
    if (filter !== "PASS" && filter !== ".") {
      issues.push(issue("warning", file, lineNumber, `${id || "variant"} has FILTER=${filter}.`));
    }
    if (depth > 0 && depth < 20) {
      issues.push(issue("warning", file, lineNumber, `${id || "variant"} has low depth (${depth}).`));
    }
  });

  return issues;
}

function validateGtfGff(file, text) {
  const issues = [];
  const styles = new Set();

  text.split(/\r?\n/).forEach((line, index) => {
    const stripped = line.trim();
    if (!stripped || stripped.startsWith("#")) return;

    const fields = line.split(/\t/);
    const lineNumber = index + 1;
    if (fields.length < 9) {
      issues.push(issue("error", file, lineNumber, "GTF/GFF rows need 9 tab-separated columns."));
      return;
    }

    const [seqid, , type, startText, endText, score, strand, phase, attributes] = fields;
    const start = Number(startText);
    const end = Number(endText);
    styles.add(seqid.startsWith("chr") ? "chr" : "bare");

    if (!type) {
      issues.push(issue("warning", file, lineNumber, "GTF/GFF feature type is empty."));
    }
    if (!Number.isInteger(start) || !Number.isInteger(end)) {
      issues.push(issue("error", file, lineNumber, "GTF/GFF start and end must be integer coordinates."));
    } else if (start < 1 || end < start) {
      issues.push(issue("error", file, lineNumber, "GTF/GFF uses 1-based closed coordinates; require 1 <= start <= end."));
    }
    if (score && score !== "." && Number.isNaN(Number(score))) {
      issues.push(issue("warning", file, lineNumber, "GTF/GFF score should be numeric or '.'."));
    }
    if (!["+", "-", ".", "?"].includes(strand)) {
      issues.push(issue("warning", file, lineNumber, "GTF/GFF strand should be '+', '-', '.', or '?'."));
    }
    if (!["0", "1", "2", "."].includes(phase)) {
      issues.push(issue("warning", file, lineNumber, "GTF/GFF phase should be 0, 1, 2, or '.'."));
    }
    if (!attributes || attributes === ".") {
      issues.push(issue("warning", file, lineNumber, "GTF/GFF attributes are missing; gene/transcript joins may fail."));
    }
  });

  if (styles.size > 1) {
    issues.push(issue("warning", file, 1, "Mixed chromosome naming styles can break annotation joins with BED/VCF/BAM files."));
  }

  return issues;
}

function validateFastq(file, text) {
  const issues = [];
  const lines = text.split(/\r?\n/);
  if (lines.length && lines[lines.length - 1] === "") {
    lines.pop();
  }

  if (lines.length === 0) {
    issues.push(issue("error", file, 1, "FASTQ file is empty."));
    return issues;
  }

  if (lines.length % 4 !== 0) {
    issues.push(issue("error", file, 1, "FASTQ records must use 4 lines per read."));
  }

  const recordCount = Math.floor(lines.length / 4);
  for (let recordIndex = 0; recordIndex < recordCount; recordIndex += 1) {
    const offset = recordIndex * 4;
    const header = lines[offset] || "";
    const sequence = lines[offset + 1] || "";
    const plus = lines[offset + 2] || "";
    const quality = lines[offset + 3] || "";
    const lineNumber = offset + 1;

    if (!header.startsWith("@")) {
      issues.push(issue("error", file, lineNumber, "FASTQ record header must start with '@'."));
    }
    if (!sequence) {
      issues.push(issue("error", file, lineNumber + 1, "FASTQ sequence line is empty."));
    } else if (/[^ACGTNacgtn.]/.test(sequence)) {
      issues.push(issue("warning", file, lineNumber + 1, "FASTQ sequence contains non-ACGTN bases."));
    }
    if (!plus.startsWith("+")) {
      issues.push(issue("error", file, lineNumber + 2, "FASTQ separator line must start with '+'."));
    }
    if (sequence.length !== quality.length) {
      issues.push(issue("error", file, lineNumber + 3, "FASTQ sequence and quality lengths must match."));
    }
  }

  return issues;
}

function validateMetadata(file, text, options = {}) {
  try {
    const metadata = JSON.parse(text);
    const issues = [];

    if (!metadata.reference?.genome_build) {
      issues.push(issue("warning", file, 1, "Metadata should record reference.genome_build."));
    }
    if (!metadata.reference?.annotation) {
      issues.push(issue("warning", file, 1, "Metadata should record reference.annotation."));
    }
    if (options.enableHumanDataWarnings !== false && metadata.privacy?.contains_human_data === true && !metadata.privacy?.sample_ids) {
      issues.push(issue("warning", file, 1, "Human data metadata should describe sample identifier policy."));
    }

    return issues;
  } catch (error) {
    return [issue("error", file, 1, `Metadata JSON does not parse: ${error.message}`)];
  }
}

function validateNextflow(file, text) {
  const issues = [];
  if (/splitCsv\(header:\s*true\)/.test(text) && !/validateSampleRow|duplicate|unique/.test(text)) {
    issues.push(issue("warning", file, 1, "Nextflow sample sheet rows should be validated before file tuple creation."));
  }
  if (/params\.reference/.test(text) && !/params\.annotation/.test(text)) {
    issues.push(issue("warning", file, 1, "Reference genome is configured without an annotation parameter."));
  }
  return issues;
}

function validateFiles(fileMap, options = {}) {
  const issues = [];

  for (const [file, text] of Object.entries(fileMap)) {
    const lower = file.toLowerCase();

    if (lower.endsWith("sample_sheet.csv") || lower.endsWith("samples.csv")) {
      issues.push(...validateSampleSheet(file, text));
    } else if (lower.endsWith(".bed")) {
      issues.push(...validateBed(file, text));
    } else if (lower.endsWith(".vcf")) {
      issues.push(...validateVcf(file, text));
    } else if (lower.endsWith(".gtf") || lower.endsWith(".gff") || lower.endsWith(".gff3")) {
      issues.push(...validateGtfGff(file, text));
    } else if (lower.endsWith(".fastq") || lower.endsWith(".fq")) {
      issues.push(...validateFastq(file, text));
    } else if (lower.endsWith("metadata.json") || lower.endsWith("project.json")) {
      issues.push(...validateMetadata(file, text, options));
    } else if (lower.endsWith(".nf") || lower.endsWith("nextflow.config")) {
      issues.push(...validateNextflow(file, text));
    }
  }

  return issues;
}

module.exports = {
  parseCsv,
  validateBed,
  validateFastq,
  validateFiles,
  validateGtfGff,
  validateMetadata,
  validateNextflow,
  validateSampleSheet,
  validateVcf
};
