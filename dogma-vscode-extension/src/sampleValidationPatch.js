"use strict";

const SAMPLE_TUPLE_PATTERN = ".map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }";

const SAMPLE_VALIDATION_HELPER = `def validateSampleRow(row) {
  def required = ["sample_id", "fastq_1", "fastq_2", "strandedness"]
  required.each { key ->
    if (!row[key]) {
      throw new IllegalArgumentException("sample sheet missing " + key + " for row: " + row)
    }
  }
  return row
}

`;

function applySampleValidationPatchText(text) {
  if (text.includes("def validateSampleRow")) {
    return { changed: false, reason: "already-present", text };
  }

  if (!text.includes("workflow {") || !text.includes(SAMPLE_TUPLE_PATTERN)) {
    return { changed: false, reason: "pattern-not-found", text };
  }

  const nextText = text.replace("workflow {", `${SAMPLE_VALIDATION_HELPER}workflow {`).replace(
    SAMPLE_TUPLE_PATTERN,
    ".map { row -> validateSampleRow(row) }\n    .map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }"
  );

  return { changed: nextText !== text, reason: nextText !== text ? "patched" : "pattern-not-found", text: nextText };
}

module.exports = {
  SAMPLE_TUPLE_PATTERN,
  SAMPLE_VALIDATION_HELPER,
  applySampleValidationPatchText
};
