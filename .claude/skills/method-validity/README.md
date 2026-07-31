# Dogma skills for Claude Science

Dogma's methods-graph **method-validity guardrail**, packaged for the Claude
Science Python analysis kernel. It reports grounded facts and explicit coverage
gaps before execution; it does not produce a biological verdict or grade.

## Skills

| skill | what it injects | wraps |
|---|---|---|
| [`method-validity/`](method-validity/) | `dogma_method_check(root)`, `dogma_method_assumptions(root)` | `dogma_service.build_method_guardrails` / `build_edge_evaluation_plan` |

The kernel helpers are **factual**: they report coverage gaps, missing
containers, unmet method assumptions, and unsatisfied execution gates. They never
return a support/refute verdict, a pass/fail grade, or a confidence score — the
Dogma "facts not verdicts" ledger model.

## How this relates to the repo

The source of truth for each skill is this Dogma monorepo. Each `kernel.py`
delegates to `dogma-local-service/dogma_service`, the same tested builders
used by the Dogma MCP evidence control plane. One guardrail core serves both the
MCP and Claude Science surfaces.

Install the sidecar distribution in the Python environment that runs the skill:

```bash
python -m pip install ./dogma-local-service
```

The resolver then checks, in order:

1. an explicit `service_root=` helper argument;
2. `$DOGMA_SERVICE_ROOT`;
3. the installed `dogma-local-service` distribution; and
4. parent directories of the absolute installed skill path, which supports an
   in-monorepo checkout.

If none resolves, the first helper call raises `ImportError` with a recipe —
it never returns an empty-but-successful result.

The skill deliberately does not search upward from the current analysis
workspace or trust distribution metadata found there. That workspace may be
untrusted user data and must not shadow Dogma's `dogma_service` package.

## Test

```bash
python -m pytest .claude/skills/method-validity/tests/ -q
```

## Publish into Claude Science

Publishing requires a Claude Science **`repl`** session (the stdlib-only
control-plane kernel that exposes `host.skills.*`); it cannot be done from Claude
Code. In a Claude Science repl, run:

```python
import pathlib
src = pathlib.Path("/path/to/dogma/.claude/skills/method-validity")
sk = "method-validity"
host.skills.edit(sk, "SKILL.md", (src / "SKILL.md").read_text())
host.skills.edit(sk, "kernel.py", (src / "kernel.py").read_text())
host.skills.publish(sk)                       # draft -> live skill set
host.agents.attach_skill("<profile>", sk)     # make it loadable by an agent
```

Then an agent loads it with `skill({"skill": "method-validity"})`; the tool
result lists the injected `dogma_*` names, and `dogma_method_check(root=".")` is
callable immediately. Install `dogma-local-service` in that analysis
environment first. For checkout-based development, set `DOGMA_SERVICE_ROOT` to
`/path/to/dogma` (or `/path/to/dogma/dogma-local-service`) instead.

## Roadmap

- Publish a versioned `dogma-local-service` distribution after the monorepo
  release boundary is reviewed; local and wheel installs are supported now.
- Live methods-graph (Kùzu) grounding path — the helpers currently report
  coverage gaps from the dependency-free guardrail; per-assumption grounding via
  `dogma_sdk().llm(...)` is the next slice.
- Additional skills mirroring the remaining Dogma MCP tools (claim graph,
  evidence ledger, evidence-bundle export) as demand warrants.
