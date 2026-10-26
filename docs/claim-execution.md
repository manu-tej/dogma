# Local claim execution contract

This bounded path is an offline-tested research prototype. Live Nextflow/Salmon
execution and biological validity have not been verified. Existing catalog/status
reads remain available. `POST /pipelines/execute` intentionally returns 409: it
cannot bypass a claim plan, explicit context-bound approval, trust, or preflight.
The nine stdlib sidecar tools remain feasibility/dry-run/stub-run tools.

The API server requires a configured `DOGMA_EXECUTION_WORKSPACE`, a separately
configured `DOGMA_LOCAL_EXECUTION_TOKEN` of at least 32 characters, and
`DOGMA_METHODS_GRAPH_DB` plus `DOGMA_METHODS_GRAPH_CLI` (a shell-split argv prefix,
for example `/path/to/methods-graph/.venv/bin/python -m methods_graph.cli`). The
bundled `bin/dogma methods-graph-preflight` launcher supplies the report without
requiring `dogma_service` in the API's Python installation. Missing dependencies,
configuration, pins, or preflight coverage prevent execution.

All three write endpoints require a loopback client, `Authorization: Bearer
<configured token>` and `X-Dogma-Local-Execution: explicitly-authorized`.
Cross-origin browser execution is blocked. Never commit the token or place it in
an execution specification.

1. `POST /pipelines/claims/{graph_id}/{edge_id}/plan` derives a versioned context.
2. `POST /pipelines/plans/{plan_id}/approve` accepts `context_digest` and
   `local_execution_authorized: true`; approval binds the displayed context.
3. `POST /pipelines/plans/{plan_id}/execute` consumes approval once, rechecks
   identities and `.dogma/trust.json` (`trusted` and `allow_local_operations` must
   both be true), and writes pending/terminal receipts under a unique
   `.dogma/executions/<service-generated-id>/` directory.

Plans are process-local and must be recreated after restart. Receipts and evidence
are durable; an execution receipt identity is idempotent and conflicts are refused.
Execution is awaited and bounded. Task cancellation/timeout request graceful
controller/process-group termination, wait at most two seconds, and then use a
bounded kill fallback. Receipts retain observed cleanup status; child processes
and Docker-container cleanup remain unverified. These events create no evidence.
The legacy external execution-status/cancel API does not manage these new awaited
claim runs; external claim-run cancellation is currently unsupported. The executor observes the
actual Nextflow version before launch and records argv, version, status, times,
and output hashes. Version checking and execution share an explicit environment
containing server-owned HOME/PATH, the pinned NXF_VER, and configured NXF_HOME,
JAVA_HOME or NXF_JAVA_HOME. Cache/Java settings are recorded without importing
other ambient environment variables. A generated `-C` configuration excludes ambient Nextflow
configuration and selects local execution with Docker through a `withName: ".*"`
executor selector, which overrides process directives. Nonlocal/dynamic workflow
executor declarations are also refused. This follows
[Nextflow selector priority](https://docs.seqera.io/nextflow/config#selector-priority).

The server-owned specification is JSON at
`.dogma/execution-specs/<sha256-of-canonical-[graph_id,edge_id]>.json`; compute the
name with `quration.pipelines.execution_contract.digest([graph_id, edge_id])[7:]`.
It is included in the content pins. A minimal shape is:

```json
{
  "readout": "transcript_abundance",
  "assay": "bulk_rnaseq",
  "data_accession": "dataset-identifier",
  "transcript_id": "ENST000001",
  "sample_id": "sample1",
  "dataset": ["reads.fastq"],
  "sample_design": "samples.csv",
  "contrast": {"kind": "single_sample", "sample_id": "sample1"},
  "workflow_files": ["main.nf"],
  "pipeline_version": "1.0.0",
  "runtime_version": "24.10.0",
  "containers": ["salmon@sha256:<64 lowercase hex characters>"],
  "parameters": {},
  "method_bindings": {
    "SALMON": {"method_id": "m:salmon", "code_digest": "sha256:<main.nf digest>"}
  }
}
```

The initial supported workflow scope is exactly one complete `.nf` file, matching
all preflight workflow files/processes. Includes, plugins, modules, unknown steps,
dynamic/unpinned containers, unbound runtime versions, reserved parameter
substitutions and symlinks in pinned inputs or measurement artifacts are refused.
Nextflow scratch work files, including normal staged-input symlinks, are excluded
from the receipt artifact manifest. The manifest covers the declared quant.sf
readout and explicit execution config/log/report files. Each process has an explicit code-digest
and method binding. The prototype checks that the workflow declares or references
`params.input` and `params.reads`; these and `--outdir` are set from the pinned
context by the executor. This syntactic check does not prove that arbitrary
workflow code semantically consumes the approved inputs. A version
label is recorded alongside the actual complete workflow digest.

The single supported design schema is CSV `sample,fastq`, containing exactly one
unique approved sample whose read file is the exact bound dataset file. The
Salmon adapter reads `results/salmon/<sample_id>/quant.sf` with the documented
`Name, Length, EffectiveLength, TPM, NumReads` TSV columns. Every row must be
well-formed, unique and finite/nonnegative. It accepts only an exact Ensembl
transcript target, a dataset source grounding matching the accession, and the
observational relation `has_transcript_abundance`. Other claims/readouts retain
receipts without measurements. TPM is relative abundance and NumReads is estimated
assigned fragments; neither is differential expression, a causal effect, a protein
measurement, or phosphorylation. The documented format is
[Salmon quant.sf](https://salmon.readthedocs.io/en/stable/file_formats.html).

Evidence records factual observations and an inconclusive direction, never a
support/refute verdict or confidence. Successful process exit without a valid,
compatible readout creates no measurement. Input/design/workflow/specification,
method database/lock, artifact, grounding and proposed-test changes make old
measurements ineligible on retrieval, including after SQLite reopen. History is
retained. Cosmetic node coordinates do not change eligibility. An external method
binding requires current server configuration pointing at that authority; absent
configuration makes its integrity unverified/ineligible. Legacy records acquire
no invented execution context or receipt.
