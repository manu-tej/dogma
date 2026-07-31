---
name: method-validity
description: "Use this skill whenever you are about to plan, choose, or run a bioinformatics analysis method in a workspace — alignment, quantification, differential expression, variant calling, peak calling, any nf-core / Nextflow step — and BEFORE you execute it. It reports factual method-validity checks for the workspace: which workflow steps have a grounded method contract, which are coverage gaps, which containers/versions are missing, which per-method assumptions and preconditions are unmet, and which execution gates (dry-run, trust, validation) are unsatisfied. Reach for it any time you need to justify a method choice, sanity-check that a pipeline's assumptions hold, or record what is unproven before running — even if the user only says 'run the DE analysis' or 'align these reads' without asking for a check. Outputs are FACTS (gaps, containers, unmet assumptions), never a support/refute verdict, a pass/fail grade, or a confidence score."
license: MIT
---

# Method Validity — factual guardrails for compbio methods

Before an analysis runs, this skill answers a factual question about the
workspace: *for each method the workflow is about to use, is its contract
grounded, are its assumptions met, is a container pinned, and are the execution
gates satisfied?* It never answers "is this result correct" — it surfaces what
is grounded and what is a coverage gap, and leaves the verdict to a human. This
is the Dogma methods-graph guardrail, delivered as a Claude Science skill.

Loading this skill auto-injects two helpers into the Python kernel (from
`kernel.py`); call them directly, no import:

| helper | when | returns |
|---|---|---|
| **`dogma_method_check(root=".")`** | before running anything — "is this workspace's method use grounded?" | guardrail report: `summary{pass,warning,gap,blocked}`, `workflow_steps[]` (each with `method_contract` + `container`), `checks[]` (factual `status`/`code`/`principle`/`detail`) |
| **`dogma_method_assumptions(root=".")`** | choosing/justifying a method — "what does this method assume, and what's unproven?" | edge plan: `task_class`, `contracts[]` (per-method assumptions + grounding), `coverage_gaps[]`, `next_actions[]`, `invariants{}` |
| **`dogma_journal(root=".")`** | at the **start** of a session — "what has already been done here?" | `summary{}`, `observed[]` (written by the service inside the function that acted), `reported[]` (agent claims) |
| **`dogma_record_decision(root=".", agent=, about=, chose=, because=, over=, supersedes=)`** | when you pick a method — so the next session does not re-litigate it | the appended entry. Stored as a **self-reported claim**; `because` is required |
| **`dogma_check_claim_shape(root=".")`** | before **reporting a conclusion** — "does any edge claim a measurement the record cannot support?" | `findings[]` (`code`/`detail`), `edges{by_state}`, `limitations[]` |

Both wrap the tested, dependency-free Dogma builders in `dogma_service`,
the same source of truth the Dogma MCP evidence control plane uses.

## Setup

Install `dogma-local-service` in the same Python environment as the analysis
kernel. The helper discovers the installed distribution without relying on the
analysis workspace:

```bash
python -m pip install /path/to/dogma/dogma-local-service
```

For checkout-based development, point the helper at either the Dogma monorepo
or its service directory:

```python
import os
os.environ["DOGMA_SERVICE_ROOT"] = "/path/to/dogma"
```

Resolution prefers an explicit `service_root=` argument, then the environment
variable, then the installed distribution, then parent search from this
skill's absolute file path. It never searches the current analysis workspace.
The first helper call raises `ImportError` with an actionable recipe if all
options fail; it never silently returns an empty result.

## Recipe — check before you run

```python
r = dogma_method_check(root=".")
s = r["summary"]
print(f"pass={s['pass']} warning={s['warning']} gap={s['gap']} blocked={s['blocked']}")
for step in r["workflow_steps"]:
    mc = (step.get("method_contract") or {}).get("method_id") or "COVERAGE GAP"
    print(f"- {step['name']}  method={mc}  container={step.get('container') or 'missing'}")
for c in r["checks"]:
    if c["status"] in ("gap", "blocked", "warning"):
        print(f"  [{c['status']}] {c['code']}: {c['detail']}")
```

A `blocked` check means an execution gate is unmet — record or resolve it before
running the real pipeline. A `gap` means no grounded method contract was found
for that step; treat it as *unproven*, not as *fine*.

## Recipe — inspect a method's assumptions

```python
p = dogma_method_assumptions(root=".")
print(f"task_class={p['task_class']}  status={p['status']}")
# contracts are per-STAGE (Readout / Grounding / Compose / Execute / Interpret),
# each with factual `facts`. The Grounding stage's facts carry `assumptions`.
for contract in p["contracts"]:
    print(f"\n{contract['stage']} ({contract['status']}): {contract['detail']}")
    for a in contract.get("facts", {}).get("assumptions", []):
        print(f"  assumption: {a}")
for gap in p["coverage_gaps"]:
    print(f"coverage gap: {gap}")
```

Use the Grounding stage's `contracts[].facts["assumptions"]` to state, in your
own analysis notes, *what the method requires for its output to mean what you'll
claim it means*. Use `coverage_gaps` to name what is unproven. Do not collapse
either into a "validated"/"invalid" label — that judgment is the scientist's.

## Recipe — the bench journal

Dogma keeps an append-only record at `<workspace>/.dogma/journal.ndjson` so the
work survives the session. Two halves, and confusing them is the one mistake
that matters:

```python
j = dogma_journal(root=".")
for e in j["observed"]:   # the service did this, inside the function that acted
    print(e["recorded_at"], e["kind"], e["body"].get("argv") or e["body"].get("target_file"))
for e in j["reported"]:   # an agent claimed this; nothing verified it
    print(e["recorded_at"], e["agent"], e["body"]["chose"], "because", e["body"]["because"])
```

Record a choice so the next session inherits the reasoning rather than the
conclusion alone:

```python
dogma_record_decision(
    root=".", agent="claude-code",
    about="aligner for the RNA-seq quantification step",
    chose="STAR",
    because="the GTF phase column is invalid, so a splice-aware aligner needs that fixed first",
    over="salmon",
)
```

Then, **before you state a conclusion**:

```python
s = dogma_check_claim_shape(root=".")
for f in s["findings"]:
    print(f["code"], f["edge_id"], f["detail"])
for note in s["limitations"]:
    print("limitation:", note)
```

`UNSUPPORTED_MEASUREMENT_CLAIM` means an edge's state says a measurement landed
and the record contains none. Report it as that — a gap in the record — not as
evidence the biology is wrong.

Read `limitations` before quoting a clean result. **No journal entry can support
an `EXAMINED` edge**: the only commands this service can run are dry-run and
stub-run, so the strongest thing the record can hold is a compile check. A
`consistent: true` therefore means "nothing claims more than the record shows",
never "everything was measured".

## Facts, not verdicts

This skill deliberately returns no boolean validity, no numeric score, and no
biological support/refute verdict. `dogma_method_assumptions(...)["invariants"]`
asserts this (`stores_biological_verdicts: False`,
`stores_confidence_grades: False`). The helpers give you grounded facts and
explicit gaps; you and the user decide what they mean. If you want a rendered
markdown version of either report, pass `include_markdown=True`.

## When NOT to use this skill

- Pure data wrangling with no method choice (reformatting a CSV, renaming
  files) — there is no method contract to check.
- After a run, to interpret results into a claim — that's a human judgment; this
  skill only reports method grounding and assumptions, never result validity.
