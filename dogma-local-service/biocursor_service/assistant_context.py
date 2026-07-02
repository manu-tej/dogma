"""Privacy-aware assistant context bundles for Dogma."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .indexer import scan_workspace


def list_text(items: list[Any] | tuple[Any, ...] | None) -> str:
    if not items:
        return "not detected"
    return ", ".join(str(item) for item in items)


def issue_location(issue: dict[str, Any]) -> str:
    return f"{issue.get('file', 'workspace')}:{issue.get('line', 1)}"


def escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def build_sample_redactor(sample_ids: list[str], enabled: bool) -> tuple[dict[str, str], Any]:
    ordered = []
    seen = set()
    for sample_id in sample_ids:
        value = str(sample_id).strip()
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)

    aliases = {sample_id: f"<sample:{index}>" for index, sample_id in enumerate(ordered, start=1)}

    def redact_text(value: str) -> str:
        if not enabled:
            return value
        text = value
        for sample_id in sorted(aliases, key=len, reverse=True):
            text = text.replace(sample_id, aliases[sample_id])
        return text

    return aliases, redact_text


def redact_value(value: Any, redact_text: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item, redact_text) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item, redact_text) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item, redact_text) for key, item in value.items()}
    return value


def build_prompt_templates(redacted: dict[str, Any]) -> dict[str, str]:
    privacy = redacted["redaction"]
    privacy_rule = (
        "Sample identifiers are redacted. Treat aliases such as <sample:1> as stable sample handles and do not ask for raw IDs unless they are required."
        if privacy["sample_ids_redacted"]
        else "Raw sample identifiers are available because the workspace trust policy allows local human-data operations or human data was not detected."
    )

    base = [
        "You are Dogma, an AI bioinformatics IDE assistant.",
        privacy_rule,
        "Use only the workspace facts in the Dogma Assistant Context Bundle. Do not invent sample metadata, clinical interpretations, reference files, or workflow outputs.",
        "Prefer narrow, reviewable workflow edits and synthetic regression fixtures.",
    ]

    return {
        "review": "\n".join(base + ["Review the bundle and list the highest-risk bioinformatics issues first, with file-backed evidence."]),
        "debug": "\n".join(base + ["Debug the current findings and explain which errors must be fixed before any real workflow run."]),
        "patch": "\n".join(base + ["Propose the smallest workflow-safe patch. Include what to test and what not to mutate."]),
        "test": "\n".join(base + ["Design synthetic fixtures and dry-run checks that cover the reported findings without using private human data."]),
    }


def render_markdown(bundle: dict[str, Any]) -> str:
    context = bundle["context"]
    summary = bundle["summary"]
    trust = bundle["trust"]
    redaction = bundle["redaction"]
    samples = context.get("samples", {})
    reference = context.get("reference", {})
    data_inventory = context.get("data_inventory", {})

    issue_rows = [
        f"| {issue.get('severity', 'info')} | {issue.get('code', 'dogma.finding')} | {issue_location(issue)} | {escape_table_cell(issue.get('message', ''))} |"
        for issue in bundle["issues"]
    ] or ["| pass | none | workspace | No Dogma findings are currently reported. |"]

    file_rows = [
        f"| {item.get('type', 'unknown')} | {item.get('path', 'unknown')} | {item.get('size', 0)} |"
        for item in bundle["files"][:50]
    ] or ["| none | not detected | 0 |"]

    fastq_rows = [
        f"| {item.get('path')} | {item.get('reads', 0)} | {item.get('bases', 0)} | {item.get('gc_percent', 'not reported')} | {item.get('min_read_length', 0)}-{item.get('max_read_length', 0)} |"
        for item in context.get("fastq_files", [])
    ] or ["| none | 0 | 0 | not reported | 0-0 |"]

    prompt_sections = []
    for name, prompt in bundle["prompts"].items():
        prompt_sections.extend([f"### {name.title()}", "", "```text", prompt, "```", ""])

    return "\n".join(
        [
            "# Dogma Assistant Context Bundle",
            "",
            "## Privacy Boundary",
            "",
            f"- Human data detected: {str(bool(trust.get('human_data'))).lower()}",
            f"- Trust status: {trust.get('status', 'unknown')}",
            f"- Workspace trusted: {str(bool(trust.get('trusted'))).lower()}",
            f"- Sample IDs redacted: {str(bool(redaction.get('sample_ids_redacted'))).lower()}",
            f"- Redaction reason: {redaction.get('reason', 'not reported')}",
            "",
            "## Workspace Summary",
            "",
            f"- Risk level: {summary.get('risk_level', 'unknown')}",
            f"- Errors: {summary.get('errors', 0)}",
            f"- Warnings: {summary.get('warnings', 0)}",
            f"- Assay: {context.get('assay') or 'not detected'}",
            f"- Organism: {context.get('organism') or 'not detected'}",
            f"- Sample sheet: {context.get('sample_file') or 'not detected'}",
            f"- Samples: {samples.get('count', 0)}",
            f"- Sample IDs: {list_text(samples.get('ids'))}",
            f"- Conditions: {list_text(samples.get('conditions'))}",
            f"- Strandedness: {list_text(samples.get('strandedness'))}",
            f"- Genome build: {reference.get('genome_build') or 'not detected'}",
            f"- Annotation: {reference.get('annotation') or 'not detected'}",
            "",
            "## Workflow And Data",
            "",
            f"- Workflow engines: {list_text(context.get('workflow_engines'))}",
            f"- Workflow files: {list_text(context.get('workflow_files'))}",
            f"- Workflow processes: {list_text(context.get('workflow_processes'))}",
            f"- Workflow includes: {list_text(context.get('workflow_includes'))}",
            f"- BED files: {list_text([item.get('path') for item in context.get('bed_files', [])])}",
            f"- VCF files: {list_text([item.get('path') for item in context.get('vcf_files', [])])}",
            f"- FASTQ inventory: {list_text(data_inventory.get('fastq'))}",
            f"- BAM inventory: {list_text(data_inventory.get('bam'))}",
            f"- CRAM inventory: {list_text(data_inventory.get('cram'))}",
            "",
            "## FASTQ QC",
            "",
            "| Path | Reads | Bases | GC % | Read length range |",
            "| --- | --- | --- | --- | --- |",
            *fastq_rows,
            "",
            "## Findings",
            "",
            "| Severity | Code | Location | Message |",
            "| --- | --- | --- | --- |",
            *issue_rows,
            "",
            "## Indexed Files",
            "",
            "| Type | Path | Size bytes |",
            "| --- | --- | --- |",
            *file_rows,
            "",
            "## Prompt Templates",
            "",
            *prompt_sections,
        ]
    )


def build_assistant_context(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    scan = scan_workspace(root, max_files=max_files)
    raw_context = scan.get("context", {})
    raw_samples = raw_context.get("samples", {})
    sample_ids = [str(item) for item in raw_samples.get("ids", []) if str(item).strip()]
    trust = scan.get("trust", {})
    should_redact = bool(trust.get("human_data") and not trust.get("trusted"))
    aliases, redact_text = build_sample_redactor(sample_ids, should_redact)

    redaction = {
        "sample_ids_redacted": should_redact,
        "sample_id_aliases": list(aliases.values()) if should_redact else [],
        "redacted_sample_id_count": len(aliases) if should_redact else 0,
        "reason": (
            "Human data was detected and the workspace trust policy does not allow local disclosure of raw sample identifiers."
            if should_redact
            else "No sample identifier redaction was required by the current trust boundary."
        ),
    }

    bundle = {
        "service": scan.get("service", "dogma-local-service"),
        "version": scan.get("version"),
        "root": str(Path(root).expanduser().resolve()),
        "redaction": redaction,
        "trust": redact_value(trust, redact_text),
        "summary": redact_value(scan.get("summary", {}), redact_text),
        "context": redact_value(raw_context, redact_text),
        "issues": redact_value(scan.get("issues", []), redact_text),
        "files": redact_value(scan.get("files", []), redact_text),
    }
    bundle["prompts"] = build_prompt_templates(bundle)
    bundle["markdown"] = render_markdown(bundle)
    return bundle
