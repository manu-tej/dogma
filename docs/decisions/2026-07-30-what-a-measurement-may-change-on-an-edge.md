# What a measurement may change on an edge

Status: **proposed** — implemented for the state rollup; the loop-selection half is
deliberately left open (see "Not decided here").

Date: 2026-07-30

## Why this note exists before the code

`rollup_edge` in `hypothesis/evidence.py` hardcodes confidence to `0.0`, and
`dataset_validation_for` returns `None` unconditionally with the comment "the
dataset channel no longer renders a verdict (north-star §2.2): support and
contradiction are abolished".

That is a deliberate, and correct, instinct. An LLM-driven engine that can propose
hypotheses cheaply must not also be the thing that declares them supported. But it
left a gap: if a measurement may not produce a verdict, what *may* it change? With
no answer, "close the loop" has no target, and any patch written to close it gets
reverted by the same reasoning that removed the last one.

## The defect this resolves

Asked a question with no usable measurement available, the loop reports itself
finished having measured nothing:

```
iter 0: edge=e-egfr-kras  direction=inconclusive magnitude='COVERAGE_GAP' weight=0.01
iter 1: edge=e-kras-resist direction=inconclusive magnitude='COVERAGE_GAP' weight=0.01
iter 2: next_proposal -> None            (loop reports DONE)
FINAL:  e-egfr-kras state=examined | e-kras-resist state=examined
```

Both edges end `examined`. Neither was measured. `rollup_edge` returns `EXAMINED`
for *any* ledger entry, and the only runner wired into the loop
(`MethodsGraphEvaluationRunner`) emits an entry for every edge it looks at —
including `COVERAGE_GAP`, which is a record of **failing** to find a method.

The deeper version, found while implementing this: that runner never emits a
measurement at all. Every entry it produces is
`direction=INCONCLUSIVE, weight=0.01, magnitude=<verdict>` where the verdict is one
of `GROUNDED` / `PARTIALLY_GROUNDED` / `COVERAGE_GAP` / `NOT_EVALUABLE`. All four
are *pre-execution feasibility assessments*. So `examined` currently means "we
checked whether this could be measured" — not "we measured it".

## Decision

**A measurement may change process state, never epistemic state.**

Whether work happened, and what kind, is a fact about the system's own activity. It
is not a claim about the biology, so recording it does not reintroduce a verdict and
does not conflict with §2.2. Concretely:

1. `EvidenceEntry` gains an explicit `kind`: `MEASUREMENT` or `FEASIBILITY`.
   - It defaults to `FEASIBILITY`, not `MEASUREMENT`. Every entry any production
     path has ever written is a feasibility assessment, so this default is both
     accurate for existing rows and the conservative direction: an entry claims to
     be a measurement only when its producer says so.

2. `EdgeState` gains `ASSESSED`, and `rollup_edge` becomes:
   - no entries → `UNTESTED`
   - at least one `MEASUREMENT` → `EXAMINED`
   - otherwise → `ASSESSED` ("we looked at whether this is measurable; we have not
     measured it")

3. What a measurement still may **not** do, unchanged from §2.2: set a confidence
   number, emit `SUPPORTED` / `REFUTED` / `CONTESTED`, or produce an
   `EdgeValidation` on the dataset channel. The per-run facts live in the ledger and
   are read there, by a person or an agent.

The distinction is worth the enum member because "we have no method for this" and
"we ran the method and the result was inconclusive" are different scientific
situations that were collapsing to the same word.

## Not decided here

**Which edges the loop should re-propose.** `untested_edges()` returns only
`UNTESTED`, so under this change an `ASSESSED` edge is never re-proposed. That is
right for `COVERAGE_GAP` (retrying finds the same absent method) and wrong for
`GROUNDED` (a method exists; the edge is ready to be measured and should be next in
line). Getting that right means the loop selects on the *assessment verdict*, not
just on state — a product decision about ordering, not a correctness fix, so it is
out of scope here. `unmeasured_edges()` is added as the primitive a future selection
policy would need.

Until that lands, the honest position is: the loop stops, and the graph says
`assessed` rather than `examined`, so the output no longer claims work that did not
happen.

## How you know it worked

The reproduction above must end with both edges `assessed`, not `examined`, and
`rollup_edge` must return `EXAMINED` only when a `MEASUREMENT` entry is present.
`tests/hypothesis/test_measurement_vs_assessment.py` asserts both.
