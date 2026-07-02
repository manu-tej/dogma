"""Workspace indexing for the Dogma local companion service."""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .trust_policy import evaluate_trust

SKIP_DIRS = {".git", ".hg", ".svn", ".dogma", "__pycache__", "node_modules", ".nextflow"}
TEXT_LIMIT_BYTES = 2_000_000


@dataclass(frozen=True)
class Issue:
    severity: str
    file: str
    line: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_file(path: Path) -> str | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    suffixes = [item.lower() for item in path.suffixes]
    compressed_suffix = suffixes[-2:] if len(suffixes) >= 2 else []

    if name in {"sample_sheet.csv", "samples.csv", "sample_sheet.csv.gz", "samples.csv.gz"}:
        return "sample_sheet"
    if suffix == ".bed" or compressed_suffix == [".bed", ".gz"]:
        return "bed"
    if suffix == ".vcf" or compressed_suffix == [".vcf", ".gz"]:
        return "vcf"
    if suffix in {".gtf", ".gff", ".gff3"} or compressed_suffix in [[".gtf", ".gz"], [".gff", ".gz"], [".gff3", ".gz"]]:
        return "annotation"
    if name in {"metadata.json", "project.json"}:
        return "metadata_json"
    if suffix == ".nf" or name == "nextflow.config":
        return "nextflow"
    if name == "snakefile" or suffix in {".smk", ".snakefile"}:
        return "snakemake"
    if suffix == ".fai":
        return "fasta_index"
    if name == "multiqc_general_stats.txt":
        return "multiqc_general_stats"
    if suffix in {".fastq", ".fq"} or suffixes[-2:] in [[".fastq", ".gz"], [".fq", ".gz"]]:
        return "fastq"
    if suffix == ".bam":
        return "bam"
    if suffix == ".cram":
        return "cram"
    return None


def iter_candidate_files(root: Path, max_files: int) -> Iterable[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS and not name.startswith("."))
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if classify_file(path) is None:
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def read_text_limited(path: Path) -> tuple[str, bool]:
    if path.suffix.lower() == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            text = handle.read(TEXT_LIMIT_BYTES + 1)
        return text[:TEXT_LIMIT_BYTES], len(text) > TEXT_LIMIT_BYTES

    data = path.read_bytes()
    truncated = len(data) > TEXT_LIMIT_BYTES
    return data[:TEXT_LIMIT_BYTES].decode("utf-8", errors="replace"), truncated


def add_issue(issues: list[Issue], severity: str, file: str, line: int, code: str, message: str) -> None:
    issues.append(Issue(severity=severity, file=file, line=line, code=code, message=message))


def sniff_delimiter(text: str) -> str:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t").delimiter
    except csv.Error:
        return "\t" if "\t" in sample and "," not in sample else ","


def parse_table(text: str) -> tuple[list[str], list[dict[str, str]]]:
    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = [{key or "": value or "" for key, value in row.items()} for row in reader]
    return reader.fieldnames or [], rows


def parse_sample_sheet(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    headers, rows = parse_table(text)
    normalized_headers = {header.strip().lower(): header for header in headers}
    required = ["sample_id", "fastq_1", "fastq_2", "condition"]

    for column in required:
        if column not in normalized_headers:
            add_issue(issues, "error", rel, 1, "sample_sheet.missing_column", f"Sample sheet is missing required column '{column}'.")

    sample_key = normalized_headers.get("sample_id")
    fastq_1_key = normalized_headers.get("fastq_1")
    fastq_2_key = normalized_headers.get("fastq_2")
    condition_key = normalized_headers.get("condition")
    strandedness_key = normalized_headers.get("strandedness")

    seen: dict[str, int] = {}
    strandedness_values: set[str] = set()
    conditions: set[str] = set()
    sample_ids: list[str] = []

    for index, row in enumerate(rows, start=2):
        sample_id = row.get(sample_key, "").strip() if sample_key else ""
        if not sample_id:
            add_issue(issues, "error", rel, index, "sample_sheet.blank_sample_id", "Sample row has a blank sample_id.")
        elif sample_id in seen:
            add_issue(issues, "error", rel, index, "sample_sheet.duplicate_sample_id", f"Duplicate sample_id '{sample_id}' was first seen on line {seen[sample_id]}.")
        else:
            seen[sample_id] = index
            sample_ids.append(sample_id)

        fastq_1 = row.get(fastq_1_key, "").strip() if fastq_1_key else ""
        fastq_2 = row.get(fastq_2_key, "").strip() if fastq_2_key else ""
        if fastq_1_key and fastq_2_key and bool(fastq_1) != bool(fastq_2):
            add_issue(issues, "error", rel, index, "sample_sheet.missing_fastq_pair", "FASTQ pair is incomplete; fastq_1 and fastq_2 should both be present for paired-end samples.")

        if condition_key and row.get(condition_key, "").strip():
            conditions.add(row[condition_key].strip())
        if strandedness_key and row.get(strandedness_key, "").strip():
            strandedness_values.add(row[strandedness_key].strip().lower())

    if len(strandedness_values) > 1:
        add_issue(issues, "warning", rel, 1, "sample_sheet.mixed_strandedness", f"Mixed strandedness values detected: {', '.join(sorted(strandedness_values))}.")

    context["sample_file"] = rel
    context["samples"]["count"] = len(rows)
    context["samples"]["ids"] = sample_ids[:100]
    context["samples"]["conditions"] = sorted(conditions)
    context["samples"]["strandedness"] = sorted(strandedness_values)


def parse_bed(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    chrom_styles: set[str] = set()
    intervals = 0

    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) < 3:
            add_issue(issues, "error", rel, index, "bed.too_few_columns", "BED rows need at least chrom, start, and end columns.")
            continue
        chrom, start_raw, end_raw = parts[:3]
        chrom_styles.add("chr" if chrom.startswith("chr") else "bare")
        intervals += 1

        try:
            start = int(start_raw)
            end = int(end_raw)
        except ValueError:
            add_issue(issues, "error", rel, index, "bed.non_numeric_coordinates", "BED start and end coordinates must be integers.")
            continue

        if start < 0:
            add_issue(issues, "error", rel, index, "bed.negative_start", "BED start coordinate cannot be negative.")
        if start >= end:
            add_issue(issues, "error", rel, index, "bed.invalid_interval", "BED start must be less than end.")
        if start == 1:
            add_issue(issues, "warning", rel, index, "bed.possible_one_based_start", "BED is 0-based; start value 1 often indicates 1-based coordinates were used.")

    if len(chrom_styles) > 1:
        add_issue(issues, "warning", rel, 1, "bed.mixed_chromosome_names", "Mixed chromosome naming detected; avoid combining chr-prefixed and bare contig names.")

    context["bed_files"].append({"path": rel, "intervals": intervals})


def parse_vcf(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    has_fileformat = False
    has_reference = False
    has_chrom_header = False
    records = 0
    non_pass_filters: set[str] = set()

    for index, line in enumerate(text.splitlines(), start=1):
        if line.startswith("##fileformat="):
            has_fileformat = True
        if line.startswith("##reference="):
            has_reference = True
        if line.startswith("#CHROM"):
            has_chrom_header = True
        if line.startswith("#") or not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 8:
            add_issue(issues, "error", rel, index, "vcf.too_few_columns", "VCF records need at least 8 fixed columns.")
            continue
        records += 1
        filter_value = parts[6]
        if filter_value not in {"PASS", "."}:
            non_pass_filters.add(filter_value)

    if not has_fileformat:
        add_issue(issues, "error", rel, 1, "vcf.missing_fileformat", "VCF header is missing ##fileformat.")
    if not has_chrom_header:
        add_issue(issues, "error", rel, 1, "vcf.missing_chrom_header", "VCF header is missing the #CHROM column line.")
    if not has_reference:
        add_issue(issues, "warning", rel, 1, "vcf.missing_reference", "VCF header is missing ##reference, which weakens reference-genome provenance.")
    if non_pass_filters:
        add_issue(issues, "warning", rel, 1, "vcf.non_pass_filters", f"VCF contains non-PASS filters: {', '.join(sorted(non_pass_filters))}.")

    context["vcf_files"].append({"path": rel, "records": records})


def parse_annotation(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    chrom_styles: set[str] = set()
    features = 0
    feature_types: set[str] = set()

    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            add_issue(issues, "error", rel, index, "annotation.too_few_columns", "GTF/GFF rows need 9 tab-separated columns.")
            continue

        seqid, _source, feature_type, start_raw, end_raw, score, strand, phase, attributes = parts[:9]
        chrom_styles.add("chr" if seqid.startswith("chr") else "bare")
        features += 1
        if feature_type:
            feature_types.add(feature_type)
        else:
            add_issue(issues, "warning", rel, index, "annotation.missing_feature_type", "GTF/GFF feature type is empty.")

        try:
            start = int(start_raw)
            end = int(end_raw)
        except ValueError:
            add_issue(issues, "error", rel, index, "annotation.non_numeric_coordinates", "GTF/GFF start and end coordinates must be integers.")
            continue

        if start < 1:
            add_issue(issues, "error", rel, index, "annotation.invalid_start", "GTF/GFF start coordinate must be 1 or greater.")
        if start > end:
            add_issue(issues, "error", rel, index, "annotation.invalid_interval", "GTF/GFF start must be less than or equal to end.")
        if score and score != ".":
            try:
                float(score)
            except ValueError:
                add_issue(issues, "warning", rel, index, "annotation.invalid_score", "GTF/GFF score should be numeric or '.'.")
        if strand not in {"+", "-", ".", "?"}:
            add_issue(issues, "warning", rel, index, "annotation.invalid_strand", "GTF/GFF strand should be '+', '-', '.', or '?'.")
        if phase not in {"0", "1", "2", "."}:
            add_issue(issues, "warning", rel, index, "annotation.invalid_phase", "GTF/GFF phase should be 0, 1, 2, or '.'.")
        if not attributes or attributes == ".":
            add_issue(issues, "warning", rel, index, "annotation.missing_attributes", "GTF/GFF attributes are missing; gene/transcript joins may fail.")

    if len(chrom_styles) > 1:
        add_issue(issues, "warning", rel, 1, "annotation.mixed_chromosome_names", "Mixed chromosome naming detected; avoid combining chr-prefixed and bare contig names.")

    context["annotation_files"].append({"path": rel, "features": features, "feature_types": sorted(feature_types)[:50]})


def parse_fastq(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    lines = text.splitlines()
    reads = 0
    bases = 0
    gc_bases = 0
    min_read_length: int | None = None
    max_read_length = 0

    if not lines:
        add_issue(issues, "error", rel, 1, "fastq.empty", "FASTQ file is empty.")
        context["fastq_files"].append({"path": rel, "reads": 0, "bases": 0, "gc_percent": None, "truncated": False})
        return

    if len(lines) % 4 != 0:
        add_issue(issues, "error", rel, 1, "fastq.incomplete_record", "FASTQ records must use 4 lines per read.")

    for offset in range(0, len(lines) - 3, 4):
        header, sequence, plus, quality = lines[offset : offset + 4]
        line_number = offset + 1
        reads += 1
        bases += len(sequence)
        gc_bases += sum(1 for base in sequence if base in {"G", "C", "g", "c"})
        min_read_length = len(sequence) if min_read_length is None else min(min_read_length, len(sequence))
        max_read_length = max(max_read_length, len(sequence))

        if not header.startswith("@"):
            add_issue(issues, "error", rel, line_number, "fastq.invalid_header", "FASTQ record header must start with '@'.")
        if not sequence:
            add_issue(issues, "error", rel, line_number + 1, "fastq.empty_sequence", "FASTQ sequence line is empty.")
        elif re.search(r"[^ACGTNacgtn.]", sequence):
            add_issue(issues, "warning", rel, line_number + 1, "fastq.invalid_bases", "FASTQ sequence contains non-ACGTN bases.")
        if not plus.startswith("+"):
            add_issue(issues, "error", rel, line_number + 2, "fastq.invalid_separator", "FASTQ separator line must start with '+'.")
        if len(sequence) != len(quality):
            add_issue(issues, "error", rel, line_number + 3, "fastq.quality_length_mismatch", "FASTQ sequence and quality lengths must match.")

    gc_percent = round((gc_bases / bases) * 100, 2) if bases else None
    context["fastq_files"].append(
        {
            "path": rel,
            "reads": reads,
            "bases": bases,
            "gc_percent": gc_percent,
            "min_read_length": min_read_length or 0,
            "max_read_length": max_read_length,
        }
    )


def parse_metadata_json(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        add_issue(issues, "error", rel, error.lineno, "metadata.invalid_json", f"Metadata JSON could not be parsed: {error.msg}.")
        return

    if isinstance(data, dict):
        context["assay"] = data.get("assay") or context.get("assay")
        context["organism"] = data.get("organism") or context.get("organism")

    reference = data.get("reference", {}) if isinstance(data, dict) else {}
    if isinstance(reference, dict):
        context["reference"]["genome_build"] = reference.get("genome_build") or reference.get("build")
        context["reference"]["annotation"] = reference.get("annotation") or reference.get("gtf")

    if not context["reference"].get("genome_build"):
        add_issue(issues, "warning", rel, 1, "metadata.missing_genome_build", "Metadata is missing reference.genome_build.")
    if not context["reference"].get("annotation"):
        add_issue(issues, "warning", rel, 1, "metadata.missing_annotation", "Metadata is missing reference.annotation.")

    samples = data.get("samples", {}) if isinstance(data, dict) else {}
    if not (isinstance(samples, dict) and samples.get("sample_id_policy")):
        add_issue(issues, "warning", rel, 1, "metadata.missing_sample_id_policy", "Metadata is missing a sample identifier policy.")

    organism = str(data.get("organism", "") if isinstance(data, dict) else "").lower()
    privacy = data.get("privacy", {}) if isinstance(data, dict) else {}
    privacy_text = json.dumps(privacy).lower() if isinstance(privacy, dict) else str(privacy).lower()
    if "human" in organism or "homo sapiens" in organism:
        context["privacy"]["human_data"] = True
        if not any(token in privacy_text for token in ["de-ident", "deidentified", "consent", "irb", "phi"]):
            add_issue(issues, "warning", rel, 1, "privacy.human_data_policy_missing", "Human data is indicated but privacy/consent/de-identification posture is not explicit.")

    context["metadata_files"].append(rel)


def parse_nextflow(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    process_names = sorted(set(re.findall(r"(?m)^\s*process\s+([A-Za-z_][A-Za-z0-9_]*)", text)))
    workflow_names = sorted(set(re.findall(r"(?m)^\s*workflow(?:\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{", text)))
    include_targets = sorted(set(re.findall(r"(?m)^\s*include\s+\{([^}]+)\}", text)))

    context["workflow_files"].append(rel)
    if "nextflow" not in context["workflow_engines"]:
        context["workflow_engines"].append("nextflow")
    context["workflow_processes"].extend(name for name in process_names if name not in context["workflow_processes"])
    context["workflow_names"].extend(name for name in workflow_names if name and name not in context["workflow_names"])
    context["workflow_includes"].extend(target.strip() for target in include_targets if target.strip() not in context["workflow_includes"])

    reads_sample_sheet = "splitCsv" in text or ("fromPath" in text and re.search(r"sample|samplesheet|sample_sheet", text, re.IGNORECASE))
    has_validation = re.search(r"validate|assert|check.*sample|error\s*\(", text, re.IGNORECASE) is not None
    if reads_sample_sheet and not has_validation:
        add_issue(issues, "warning", rel, 1, "nextflow.sample_sheet_validation", "Workflow appears to read sample sheet rows without an explicit validation guard.")


def parse_fasta_index(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    contigs = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            add_issue(issues, "error", rel, index, "fai.too_few_columns", "FASTA index rows should contain at least 5 tab-separated columns.")
            continue
        try:
            length = int(parts[1])
        except ValueError:
            add_issue(issues, "error", rel, index, "fai.invalid_length", "FASTA index contig length must be an integer.")
            continue
        contigs.append({"name": parts[0], "length": length})

    context["reference"]["contigs"] = contigs[:200]


def parse_multiqc_general_stats(text: str, rel: str, issues: list[Issue], context: dict[str, Any]) -> None:
    headers, rows = parse_table(text)
    if not headers:
        add_issue(issues, "warning", rel, 1, "multiqc.empty_stats", "MultiQC general stats file has no header row.")
        return
    context["qc_reports"].append({"path": rel, "samples": len(rows), "metrics": max(len(headers) - 1, 0)})


def build_initial_context() -> dict[str, Any]:
    return {
        "assay": None,
        "organism": None,
        "sample_file": None,
        "samples": {"count": 0, "ids": [], "conditions": [], "strandedness": []},
        "reference": {"genome_build": None, "annotation": None, "contigs": []},
        "privacy": {"human_data": False},
        "workflow_files": [],
        "workflow_engines": [],
        "workflow_names": [],
        "workflow_processes": [],
        "workflow_includes": [],
        "bed_files": [],
        "vcf_files": [],
        "annotation_files": [],
        "fastq_files": [],
        "metadata_files": [],
        "qc_reports": [],
        "data_inventory": {"fastq": [], "bam": [], "cram": []},
    }


def summarize(context: dict[str, Any], issues: list[Issue]) -> dict[str, Any]:
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    risk_level = "blocked" if errors else "review" if warnings else "ready"
    return {
        "risk_level": risk_level,
        "errors": errors,
        "warnings": warnings,
        "samples": context["samples"]["count"],
        "conditions": context["samples"]["conditions"],
        "genome_build": context["reference"].get("genome_build"),
        "annotation": context["reference"].get("annotation"),
        "workflow_files": context["workflow_files"],
        "workflow_engines": context["workflow_engines"],
        "workflow_processes": context["workflow_processes"],
        "bed_files": [item["path"] for item in context["bed_files"]],
        "vcf_files": [item["path"] for item in context["vcf_files"]],
        "annotation_files": [item["path"] for item in context["annotation_files"]],
        "fastq_files": [item["path"] for item in context["fastq_files"]],
        "fastq_reads": sum(item.get("reads", 0) for item in context["fastq_files"]),
        "human_data": context["privacy"]["human_data"],
    }


def scan_workspace(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Workspace root does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Workspace root is not a directory: {root_path}")

    context = build_initial_context()
    issues: list[Issue] = []
    files: list[dict[str, Any]] = []

    for path in iter_candidate_files(root_path, max_files=max_files):
        rel = path.relative_to(root_path).as_posix()
        kind = classify_file(path)
        stat = path.stat()
        files.append({"path": rel, "type": kind, "size": stat.st_size})

        if kind in {"bam", "cram"}:
            context["data_inventory"][kind].append(rel)
            continue

        try:
            text, truncated = read_text_limited(path)
        except (OSError, EOFError, UnicodeError) as error:
            add_issue(issues, "error", rel, 1, "file.read_failed", f"Could not read candidate file: {type(error).__name__}: {error}")
            continue
        if truncated:
            add_issue(issues, "warning", rel, 1, "file.truncated", "File exceeded the local indexer's text limit; validation used the first 2 MB only.")

        if kind == "fastq":
            context["data_inventory"][kind].append(rel)
            parse_fastq(text, rel, issues, context)
        elif kind == "sample_sheet":
            parse_sample_sheet(text, rel, issues, context)
        elif kind == "bed":
            parse_bed(text, rel, issues, context)
        elif kind == "vcf":
            parse_vcf(text, rel, issues, context)
        elif kind == "annotation":
            parse_annotation(text, rel, issues, context)
        elif kind == "metadata_json":
            parse_metadata_json(text, rel, issues, context)
        elif kind == "nextflow":
            parse_nextflow(text, rel, issues, context)
        elif kind == "snakemake":
            context["workflow_files"].append(rel)
            if "snakemake" not in context["workflow_engines"]:
                context["workflow_engines"].append("snakemake")
        elif kind == "fasta_index":
            parse_fasta_index(text, rel, issues, context)
        elif kind == "multiqc_general_stats":
            parse_multiqc_general_stats(text, rel, issues, context)

    issue_dicts = [issue.to_dict() for issue in issues]
    result = {
        "service": "dogma-local-service",
        "version": __version__,
        "root": str(root_path),
        "files": files,
        "summary": summarize(context, issues),
        "context": context,
        "issues": issue_dicts,
    }
    result["trust"] = evaluate_trust(root_path, result)
    return result
