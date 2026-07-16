"""
Kernel sidecar for the ``method-validity`` Claude Science skill.

Auto-injected into the Python kernel on ``skill({"skill": "method-validity"})``.
Top level is definition-only (functions, stdlib imports, literal constants) so
the sidecar AST gate accepts it; every non-stdlib import happens inside a
function body so the sidecar also loads in the bare skeleton env. All names are
``dogma_``-prefixed since sidecars share the kernel's ``__main__``.

Primary surface:
    dogma_method_check(root=".")        — factual method guardrail report
    dogma_method_assumptions(root=".")  — per-method preconditions + coverage gaps

Both wrap the tested, dependency-free Dogma builders
(``biocursor_service.method_guardrails.build_method_guardrails`` and
``biocursor_service.edge_evaluation_plan.build_edge_evaluation_plan``) — the same
source of truth the Dogma MCP evidence control plane uses. Nothing here computes
a support/refute verdict, a confidence score, or a valid/invalid boolean:
outputs are FACTS (coverage gaps, containers, unmet assumptions, execution
gates), consistent with the Dogma "facts not verdicts" ledger model.
"""

import os
import sys


DOGMA_DEFAULT_MAX_FILES = 500
"""Default candidate-file cap passed through to the workspace scanners."""

DOGMA_SERVICE_DIRNAME = "dogma-local-service"
"""Directory (inside the Dogma monorepo) that contains the importable
``biocursor_service`` package. Its parent goes on sys.path."""

DOGMA_SERVICE_PACKAGE = "biocursor_service"
"""Package name imported from under DOGMA_SERVICE_DIRNAME."""

DOGMA_SERVICE_DISTRIBUTION = "dogma-local-service"
"""Installed distribution that owns ``biocursor_service``."""

DOGMA_REQUIRED_MODULES = ("method_guardrails.py", "edge_evaluation_plan.py")
"""Module files that must exist inside a candidate ``biocursor_service`` dir for
it to count as the real, importable Dogma service. Requiring them stops a
partial or shadow package (an empty dir of the right name) from being accepted
as the resolved root and then failing later with an opaque
``ModuleNotFoundError`` — the resolver's promise is to raise the actionable
recipe instead."""

DOGMA_MARKDOWN_KEY = "markdown"
"""Rendered-report key stripped from results by default — it is a large
human-readable dump of the same facts already present as structured fields."""


def dogma_sdk():
    """Rebind-proof SDK handle (see pdf-explore/kernel.py:pdf_sdk). Lazy so the
    sidecar still loads in the bare skeleton env, which has no ``host``. Not used
    by the v1 helpers (they make no LLM/host calls); kept for the future
    methods-graph grounding path, which will fan out per-assumption checks via
    ``dogma_sdk().llm(...)``."""
    import host
    return host


def dogma_service_root(explicit=None):
    """Resolve the filesystem dir that contains the importable
    ``biocursor_service`` package, so the sidecar can import the tested Dogma
    guardrail builders from an installed distribution or an in-repo checkout.

    Resolution order:
        1. ``explicit`` argument, if given.
        2. ``$DOGMA_SERVICE_ROOT`` env var.
        3. The installed ``dogma-local-service`` distribution.
        4. Search upward from this file's location (useful when the skill is
           run from an in-repo checkout instead of a published copy).

    Returns an absolute path to the directory that should go on ``sys.path``
    (i.e. the parent of ``biocursor_service``). Raises ``ImportError`` with an
    actionable recipe if none is found — never returns a bogus path that would
    fail with an opaque ``ModuleNotFoundError`` later.

    Deliberately does NOT search the current working directory, its descendants,
    or relative ``sys.path`` entries. In Claude Science the cwd is often an
    arbitrary analysis workspace, and importing code or distribution metadata
    discovered there would let workspace files shadow Dogma's trusted package.
    """
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("DOGMA_SERVICE_ROOT")
    if env:
        candidates.append(env)

    # A biocursor_service dir counts only if it actually contains the module
    # files we import — not merely a dir of the right name. This keeps a
    # partial/empty/shadow package from short-circuiting resolution and then
    # dying on an opaque ModuleNotFoundError at import time.
    def _is_service_package(pkg_dir):
        if not os.path.isdir(pkg_dir):
            return False
        return all(
            os.path.isfile(os.path.join(pkg_dir, module))
            for module in DOGMA_REQUIRED_MODULES
        )

    # A candidate is valid if it directly contains biocursor_service, OR it
    # contains dogma-local-service/biocursor_service (point either at the
    # service dir or at the repo root).
    def _resolve_candidate(path):
        path = os.path.abspath(os.path.expanduser(path))
        if _is_service_package(os.path.join(path, DOGMA_SERVICE_PACKAGE)):
            return path
        nested = os.path.join(path, DOGMA_SERVICE_DIRNAME)
        if _is_service_package(os.path.join(nested, DOGMA_SERVICE_PACKAGE)):
            return nested
        return None

    for cand in candidates:
        resolved = _resolve_candidate(cand)
        if resolved:
            return resolved

    def _path_is_within(path, parent):
        path = os.path.realpath(path)
        parent = os.path.realpath(parent)
        try:
            return os.path.commonpath((path, parent)) == parent
        except ValueError:
            return False

    def _normalized_distribution_name(name):
        return str(name or "").strip().lower().replace("_", "-").replace(".", "-")

    # Discover package metadata only on absolute sys.path entries outside the
    # analysis workspace. importlib.metadata otherwise treats '' as cwd and can
    # accept a forged *.dist-info directory planted beside the user's data.
    cwd = os.path.realpath(os.getcwd())
    trusted_paths = []
    for entry in sys.path:
        if not entry or not os.path.isabs(entry):
            continue
        entry = os.path.realpath(os.path.expanduser(entry))
        if _path_is_within(entry, cwd):
            continue
        if entry not in trusted_paths:
            trusted_paths.append(entry)

    try:
        import importlib.metadata as dogma_metadata
    except ImportError:
        dogma_metadata = None
    if dogma_metadata is not None:
        for distribution in dogma_metadata.distributions(path=trusted_paths):
            try:
                name = distribution.metadata.get("Name", "")
            except (AttributeError, KeyError, TypeError):
                continue
            if _normalized_distribution_name(name) != DOGMA_SERVICE_DISTRIBUTION:
                continue
            try:
                package_dir = os.path.realpath(os.fspath(
                    distribution.locate_file(DOGMA_SERVICE_PACKAGE)
                ))
            except (AttributeError, OSError, TypeError, ValueError):
                continue
            # A real distribution locates files under the search root that
            # yielded its metadata. Enforce that invariant before trusting it.
            if not any(_path_is_within(package_dir, path) for path in trusted_paths):
                continue
            if _is_service_package(package_dir):
                return os.path.dirname(package_dir)

    # Search upward only from this file, not from cwd. Cwd can be untrusted
    # analysis data; the skill file path is either the repo checkout or the
    # Claude Science installed skill path.
    starts = []
    try:
        skill_file = __file__
    except NameError:  # __file__ absent in some exec contexts
        skill_file = None
    # Only trust __file__ as a search origin if it is ABSOLUTE. A relative
    # __file__ would be resolved against cwd by abspath(), reintroducing exactly
    # the untrusted-workspace shadowing the cwd exclusion is meant to prevent.
    if skill_file and os.path.isabs(skill_file):
        starts.append(os.path.dirname(skill_file))
    for start in starts:
        cur = start
        while True:
            resolved = _resolve_candidate(cur)
            if resolved:
                return resolved
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    raise ImportError(
        "method-validity: could not locate the Dogma guardrail package "
        f"'{DOGMA_SERVICE_PACKAGE}'. Install the '{DOGMA_SERVICE_DISTRIBUTION}' "
        "distribution in this Python environment, or set DOGMA_SERVICE_ROOT "
        f"to the Dogma monorepo root (or its '{DOGMA_SERVICE_DIRNAME}' "
        "directory), e.g. os.environ['DOGMA_SERVICE_ROOT'] = "
        "'/path/to/dogma', then re-run."
    )


def dogma_load_builders(service_root=None):
    """Import and return ``(build_method_guardrails, build_edge_evaluation_plan)``
    from the resolved Dogma service, placing its parent before the analysis
    workspace on ``sys.path``. Import is done here (not at module top level) so
    the sidecar loads in the bare skeleton env; the AST gate forbids the
    non-stdlib import above."""
    root = dogma_service_root(explicit=service_root)
    root = os.path.realpath(root)
    package_dir = os.path.realpath(os.path.join(root, DOGMA_SERVICE_PACKAGE))

    def _module_is_from_package(module):
        origin = getattr(module, "__file__", None)
        if not origin:
            return False
        origin = os.path.realpath(origin)
        try:
            return os.path.commonpath((origin, package_dir)) == package_dir
        except ValueError:
            return False

    module_names = (
        DOGMA_SERVICE_PACKAGE,
        f"{DOGMA_SERVICE_PACKAGE}.method_guardrails",
        f"{DOGMA_SERVICE_PACKAGE}.edge_evaluation_plan",
    )
    for module_name in module_names:
        loaded = sys.modules.get(module_name)
        if loaded is not None and not _module_is_from_package(loaded):
            raise ImportError(
                f"method-validity: refusing already-loaded shadow module "
                f"{module_name!r} from {getattr(loaded, '__file__', None)!r}; "
                f"the resolved Dogma package is at {package_dir!r}. Restart the "
                "kernel after removing the shadow package."
            )

    # Promote the verified root even when it already appears later on sys.path;
    # leaving '' or the analysis workspace ahead of it permits import shadowing.
    sys.path[:] = [entry for entry in sys.path if entry != root]
    sys.path.insert(0, root)
    try:
        from biocursor_service.method_guardrails import build_method_guardrails
        from biocursor_service.edge_evaluation_plan import build_edge_evaluation_plan
    except ImportError as exc:
        # Belt-and-suspenders: dogma_service_root already requires the module
        # files, but if a package still fails to import (a shadow that has the
        # filenames but broken contents, a partial checkout) surface the
        # actionable recipe rather than the opaque ModuleNotFoundError.
        raise ImportError(
            f"method-validity: located a '{DOGMA_SERVICE_PACKAGE}' package at "
            f"{root!r} but could not import the Dogma guardrail builders from it "
            f"({exc}). The package may be partial or shadowed. Point "
            "DOGMA_SERVICE_ROOT at a complete Dogma monorepo checkout and "
            "re-run."
        ) from exc

    for module_name in module_names:
        loaded = sys.modules.get(module_name)
        if loaded is None or not _module_is_from_package(loaded):
            raise ImportError(
                f"method-validity: imported {module_name!r} from an unexpected "
                "location. Restart the kernel after removing any workspace "
                "package named 'biocursor_service'."
            )
    return build_method_guardrails, build_edge_evaluation_plan


def dogma_strip_markdown(obj):
    """Recursively drop every ``markdown`` key so results stay compact and
    structured. Returns a new object; does not mutate the input. The dropped
    text is a rendered view of facts already present as structured fields."""
    if isinstance(obj, dict):
        return {
            k: dogma_strip_markdown(v)
            for k, v in obj.items()
            if k != DOGMA_MARKDOWN_KEY
        }
    if isinstance(obj, list):
        return [dogma_strip_markdown(v) for v in obj]
    return obj


def dogma_method_check(root=".", max_files=DOGMA_DEFAULT_MAX_FILES,
                       include_markdown=False, service_root=None):
    """Factual method-validity report for a bioinformatics workspace.

    Wraps ``build_method_guardrails``. Returns the guardrail result dict::

        {"service", "root",
         "summary": {"pass", "warning", "gap", "blocked"},
         "workflow_steps": [{"name","file","line","method_contract","container"}],
         "checks": [{"status","code","principle","detail","evidence"}],
         "scan_summary", "trust", "sources"}

    Every entry is a FACT — a coverage gap, a missing container, an unmet
    execution gate — not a support/refute verdict or a numeric grade. Use it
    before running a method to see which steps have grounded method contracts,
    which are coverage gaps, and what must be recorded before real execution.

    ``include_markdown=True`` keeps the rendered report; default strips it.
    """
    build_method_guardrails, _ = dogma_load_builders(service_root)
    result = build_method_guardrails(root, max_files=int(max_files))
    return result if include_markdown else dogma_strip_markdown(result)


def dogma_method_assumptions(root=".", max_files=DOGMA_DEFAULT_MAX_FILES,
                             include_markdown=False, service_root=None):
    """Per-method preconditions/assumptions and coverage gaps for the
    workspace's measurable edge/task.

    Wraps ``build_edge_evaluation_plan``. Returns::

        {"service", "root", "status", "task_class",
         "edge", "selected_edge", "summary",
         "coverage_gaps": [str, ...],
         "contracts": [{"stage", "status", "detail", "facts": {...}}, ...],
         "next_actions": [str, ...],
         "invariants": {"stores_biological_verdicts": False, ...}}

    This is the helper that makes the skill "method-validity" rather than a bare
    workspace scan. ``contracts`` are per-STAGE (Readout / Grounding / Compose /
    Execute / Interpret), each carrying factual ``facts``; the Grounding stage's
    ``facts["assumptions"]`` lists the method assumptions, and ``coverage_gaps``
    name what is unproven — as facts, never a graded validity score. The
    ``invariants`` block asserts no verdicts/grades are stored.

    ``include_markdown=True`` keeps rendered reports; default strips them.
    """
    _, build_edge_evaluation_plan = dogma_load_builders(service_root)
    result = build_edge_evaluation_plan(root, max_files=int(max_files))
    return result if include_markdown else dogma_strip_markdown(result)
