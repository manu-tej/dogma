"""Does the graph's claimed state match what the journal says happened?

This is the check the journal exists to make possible, and the reason a bare log
would not have been enough.

Dogma already enforces a lot *within* one object: `EvidenceEntry` refuses to be a
MEASUREMENT without `PipelineRunProvenance`, `rollup_edge` maps assessments-only
to ASSESSED. But nothing compared the graph against the history of the
workspace. An edge could arrive claiming EXAMINED — from an import, a hand edit,
a future writer — and every per-object validator would pass, because each one
only sees the object in front of it.

So the question here is deliberately narrow and answerable:

    the graph says this edge was measured; does anything in the record
    show a measurement?

The answer is a fact, never a verdict. `UNSUPPORTED_MEASUREMENT_CLAIM` means the
record does not contain a measurement for that edge — it does not mean the claim
is false, and this module never emits SUPPORTED/REFUTED, a score, or a grade.

One asymmetry is worth stating plainly, because it looks like a bug and is not.
`build_command` can only ever emit `nextflow -stub-run` or `snakemake --dry-run`
(`execution_sandbox.build_command`), so the strongest thing the journal can ever
hold is a compile check. **No journal entry can support an EXAMINED edge**, and
this module will not invent a rule that lets one. That gap is the honest state of
the loop, and making it visible is more useful than closing it by relabelling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import journal

#: An edge reaches this only if something measured it. Mirrors
#: `quration.hypothesis.graph.EdgeState`; duplicated rather than imported because
#: this package stays dependency-free (see `quration_handoff`).
MEASURED_EDGE_STATE = "examined"

#: A feasibility verdict exists, nothing measured it. Not a problem — the state
#: most real edges legitimately reach today.
ASSESSED_EDGE_STATE = "assessed"

#: Journal kinds that record something running. None of them is a measurement,
#: by construction; see the module docstring.
RUN_KINDS = frozenset({"stub_run", "dry_run"})


def _findings_for(graph: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    runs = [e for e in entries if e.get("kind") in RUN_KINDS]

    for edge in graph.get("edges", []):
        state = edge.get("state")
        if state != MEASURED_EDGE_STATE:
            continue
        findings.append({
            "code": "UNSUPPORTED_MEASUREMENT_CLAIM",
            "edge_id": edge.get("id"),
            "detail": (
                f"edge state is {MEASURED_EDGE_STATE!r}, which means a measurement "
                "landed, but the journal records no measurement for it"
            ),
            # Stated so the reader is not left inferring it: the runs that DO
            # exist could not have supported this claim even in principle.
            "runs_in_journal": len(runs),
            "runs_are_measurements": False,
        })

    if runs and not journal_has_any_edge_reference(runs):
        findings.append({
            "code": "RUNS_NOT_LINKED_TO_ANY_EDGE",
            "edge_id": None,
            "detail": (
                f"{len(runs)} run(s) recorded, none naming the claim they bear on. "
                "The record shows work happened but not what it was for."
            ),
            "runs_in_journal": len(runs),
            "runs_are_measurements": False,
        })

    return findings


def journal_has_any_edge_reference(runs: list[dict[str, Any]]) -> bool:
    return any((run.get("body") or {}).get("edge_id") for run in runs)


def check_claim_shape(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    """Compare the workspace's claim graph against its recorded history."""
    from .quration_handoff import build_quration_handoff

    root_path = Path(root).expanduser().resolve()
    handoff = build_quration_handoff(root_path, max_files=max_files)
    graph = handoff.get("causal_graph", {})
    entries = journal.read(root_path)

    edges = graph.get("edges", [])
    findings = _findings_for(graph, entries)
    by_state: dict[str, int] = {}
    for edge in edges:
        key = str(edge.get("state"))
        by_state[key] = by_state.get(key, 0) + 1

    return {
        "contract_version": "dogma-claim-shape.v1",
        "root": str(root_path),
        "journal": journal.summary(root_path),
        "edges": {
            "total": len(edges),
            "by_state": by_state,
            "claiming_measurement": by_state.get(MEASURED_EDGE_STATE, 0),
            "assessed_only": by_state.get(ASSESSED_EDGE_STATE, 0),
        },
        "findings": findings,
        "consistent": not findings,
        "limitations": [
            # Said out loud, because a check that hides its own reach is worse
            # than no check: a clean result would read as "everything measured".
            "No journal entry can support an EXAMINED edge. The only commands "
            "this service can run are dry-run and stub-run, so the strongest "
            "record it can hold is a compile check, never a measurement.",
            "Staleness is not detected: file digests are recorded per patch, not "
            "per edge, so an input changing after an assessment is invisible here.",
            "This reports facts about the record. It never emits a "
            "SUPPORTED/REFUTED verdict, a confidence score, or a grade.",
        ],
        "invariants": {
            "stores_biological_verdicts": False,
            "stores_confidence_grades": False,
            "measurement_claims_require_journal_support": True,
        },
    }
