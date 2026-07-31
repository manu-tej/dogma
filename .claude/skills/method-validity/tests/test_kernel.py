"""Tests for the method-validity skill kernel sidecar.

The kernel helpers are pure Python wrapping the tested Dogma guardrail builders,
so we can exercise them directly (no Claude Science runtime needed). We load
kernel.py by path (it is a sidecar, not a package) and run both helpers against
a small fixture workspace and against the repo itself.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


SKILL_DIR = Path(__file__).resolve().parents[1]          # .../method-validity
REPO_ROOT = Path(__file__).resolve().parents[3]          # Dogma monorepo root


def load_kernel():
    """Import kernel.py by path as a standalone module."""
    spec = importlib.util.spec_from_file_location(
        "method_validity_kernel", SKILL_DIR / "kernel.py"
    )
    assert spec and spec.loader, "could not build import spec for kernel.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def kernel():
    # Remove any ambient DOGMA_SERVICE_ROOT so the shape tests exercise the real
    # production path — __file__ upward auto-discovery finding the in-repo
    # service — rather than a shortcut via env. Restore afterward so the env is
    # not leaked to the rest of the process.
    import os

    saved = os.environ.pop("DOGMA_SERVICE_ROOT", None)
    try:
        yield load_kernel()
    finally:
        if saved is not None:
            os.environ["DOGMA_SERVICE_ROOT"] = saved


@pytest.fixture()
def no_installed_service(monkeypatch):
    """Keep failure-path tests deterministic even when the sidecar distribution
    is installed in the environment running this suite."""
    monkeypatch.setattr(importlib.metadata, "distributions", lambda **kwargs: ())


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A minimal bioinformatics workspace: a sample sheet, a Nextflow process,
    and a metadata file — enough for the scanners to produce workflow steps and
    coverage-gap facts."""
    (tmp_path / "samplesheet.csv").write_text(
        "sample,fastq_1,fastq_2,condition\n"
        "s1,s1_R1.fastq.gz,s1_R2.fastq.gz,control\n"
        "s2,s2_R1.fastq.gz,s2_R2.fastq.gz,treated\n"
    )
    (tmp_path / "main.nf").write_text(
        "process QUANTIFY {\n"
        "  input:\n  path reads\n"
        "  output:\n  path 'quant'\n"
        "  script:\n  '''\n  salmon quant -r $reads -o quant\n  '''\n"
        "}\n"
    )
    (tmp_path / "metadata.json").write_text(
        json.dumps({"organism": "Homo sapiens", "assay": "RNA-seq"})
    )
    return tmp_path


# ── shape ────────────────────────────────────────────────────────────────────

def test_method_check_shape(kernel, workspace):
    r = kernel.dogma_method_check(root=str(workspace))
    assert isinstance(r, dict)
    assert set(["summary", "checks", "workflow_steps"]).issubset(r)
    summary = r["summary"]
    for key in ("pass", "warning", "gap", "blocked"):
        assert key in summary and isinstance(summary[key], int)
    for c in r["checks"]:
        assert set(["status", "code", "principle", "detail"]).issubset(c)


def test_method_assumptions_shape(kernel, workspace):
    p = kernel.dogma_method_assumptions(root=str(workspace))
    assert isinstance(p, dict)
    assert set(["task_class", "status", "contracts", "coverage_gaps"]).issubset(p)
    assert isinstance(p["contracts"], list)
    assert isinstance(p["coverage_gaps"], list)


# ── facts, not verdicts ──────────────────────────────────────────────────────

def test_no_verdict_or_score_keys(kernel, workspace):
    """The whole point: no boolean validity, no numeric grade, no support/refute
    verdict anywhere in the returned structures. Guards both bare tokens and the
    compound keys a regression would realistically introduce
    (``is_valid``/``confidence_score``/``validity_grade``). Deliberately does NOT
    ban ``validation_status`` — human validation state is a factual descriptor,
    not a verdict. String *values* are checked only for an exact biological
    verdict word (``supported``/``refuted``), so factual status enums
    (``coverage_gap``/``ready``/``grounded``) and prose details are unaffected."""
    banned_keys = {
        "valid", "invalid", "score", "confidence", "verdict", "supported",
        "refuted", "grade", "is_valid", "confidence_score", "validity_grade",
        "validity_score", "support_score", "refute_score",
    }
    banned_values = {"supported", "refuted"}

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k.lower() not in banned_keys, f"verdict-like key: {k!r}"
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            assert obj.strip().lower() not in banned_values, \
                f"verdict-like value: {obj!r}"

    walk(kernel.dogma_method_check(root=str(workspace)))
    walk(kernel.dogma_method_assumptions(root=str(workspace)))


def test_invariants_assert_no_verdicts(kernel, workspace):
    inv = kernel.dogma_method_assumptions(root=str(workspace))["invariants"]
    assert inv["stores_biological_verdicts"] is False
    assert inv["stores_confidence_grades"] is False
    assert inv["coverage_gaps_are_explicit"] is True


def test_markdown_stripped_by_default(kernel, workspace):
    r = kernel.dogma_method_check(root=str(workspace))
    assert "markdown" not in r
    r_md = kernel.dogma_method_check(root=str(workspace), include_markdown=True)
    assert "markdown" in r_md and isinstance(r_md["markdown"], str)


def test_markdown_strip_preserves_facts(kernel, workspace):
    """Stripping markdown must remove ONLY markdown — every structured fact
    present with include_markdown=True must survive in the default result. If a
    future backend ever moved a fact into markdown-only, this fails loudly
    instead of the default path silently hiding it."""
    full = kernel.dogma_method_check(root=str(workspace), include_markdown=True)
    stripped = kernel.dogma_method_check(root=str(workspace))
    assert stripped["summary"] == full["summary"]
    assert stripped["checks"] == full["checks"]
    assert stripped["workflow_steps"] == full["workflow_steps"]
    # The default result is exactly the full result with markdown keys dropped.
    assert kernel.dogma_strip_markdown(full) == stripped


# ── coverage gaps surface, not silently defaulted ────────────────────────────

def test_missing_contract_is_a_coverage_gap(kernel, workspace):
    """A workflow step with no grounded method contract must appear as a factual
    gap, never be silently treated as grounded/supported."""
    p = kernel.dogma_method_assumptions(root=str(workspace))
    r = kernel.dogma_method_check(root=str(workspace))
    # Either a coverage gap is named, or a check is flagged gap/blocked — the
    # fixture has no audited methods-graph substrate, so grounding is expected
    # to be incomplete and that must be visible.
    has_gap = bool(p["coverage_gaps"]) or any(
        c["status"] in ("gap", "blocked") for c in r["checks"]
    )
    assert has_gap, "missing method grounding was not surfaced as a fact"


# ── import failure is loud, not silent ───────────────────────────────────────

def test_unresolvable_service_root_raises(
    kernel, tmp_path, monkeypatch, no_installed_service
):
    """With a bogus DOGMA_SERVICE_ROOT and a cwd/skill tree that can't reach the
    service, the helper raises ImportError with a recipe — it does not return an
    empty-but-successful result. We move cwd out of the repo and point the
    module's __file__ outside the repo so neither auto-discovery path finds the
    in-repo service."""
    outside = tmp_path / "sandbox"
    outside.mkdir()
    monkeypatch.setenv("DOGMA_SERVICE_ROOT", str(tmp_path / "nowhere"))
    monkeypatch.chdir(outside)
    monkeypatch.setattr(kernel, "__file__", str(outside / "kernel.py"))
    # match= pins the ACTIONABLE recipe error — ModuleNotFoundError is an
    # ImportError subclass, so a bare pytest.raises(ImportError) would also pass
    # on an opaque late import failure, masking loss of the recipe.
    with pytest.raises(ImportError, match=r"DOGMA_SERVICE_ROOT"):
        kernel.dogma_service_root()


def test_cwd_shadow_service_is_not_auto_imported(
    kernel, tmp_path, monkeypatch, no_installed_service
):
    """The sidecar must not import a dogma-local-service tree discovered only
    from cwd. Claude Science workspaces can be arbitrary user data, so cwd-based
    package discovery is a code-execution footgun."""
    workspace = tmp_path / "workspace"
    fake_package = workspace / "dogma-local-service" / "dogma_service"
    fake_package.mkdir(parents=True)
    (fake_package / "__init__.py").write_text("")
    outside_skill = tmp_path / "installed-skill" / "method-validity" / "kernel.py"
    outside_skill.parent.mkdir(parents=True)

    monkeypatch.delenv("DOGMA_SERVICE_ROOT", raising=False)
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(kernel, "__file__", str(outside_skill))

    with pytest.raises(ImportError, match=r"DOGMA_SERVICE_ROOT"):
        kernel.dogma_service_root()


def test_relative_file_does_not_reintroduce_cwd(
    kernel, tmp_path, monkeypatch, no_installed_service
):
    """A RELATIVE __file__ must not be trusted as a search origin: abspath() would
    resolve it against cwd and reintroduce the untrusted-workspace shadowing the
    cwd exclusion prevents. We plant a *complete-looking* fake service in cwd
    (real module filenames) and set __file__ to a bare relative name; resolution
    must still raise the recipe rather than pick up the cwd package."""
    workspace = tmp_path / "workspace"
    fake_pkg = workspace / "dogma-local-service" / "dogma_service"
    fake_pkg.mkdir(parents=True)
    (fake_pkg / "__init__.py").write_text("")
    (fake_pkg / "method_guardrails.py").write_text("")
    (fake_pkg / "edge_evaluation_plan.py").write_text("")

    monkeypatch.delenv("DOGMA_SERVICE_ROOT", raising=False)
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(kernel, "__file__", "kernel.py")  # relative
    with pytest.raises(ImportError, match=r"DOGMA_SERVICE_ROOT"):
        kernel.dogma_service_root()


def test_partial_package_via_env_raises_recipe(
    kernel, tmp_path, monkeypatch, no_installed_service
):
    """A dir named dogma_service that lacks the imported module files must be
    rejected — resolution raises the actionable recipe, not an opaque
    ModuleNotFoundError at import time."""
    root = tmp_path / "checkout"
    empty_pkg = root / "dogma_service"
    empty_pkg.mkdir(parents=True)
    (empty_pkg / "__init__.py").write_text("")  # no method_guardrails.py etc.

    monkeypatch.setenv("DOGMA_SERVICE_ROOT", str(root))
    monkeypatch.setattr(kernel, "__file__", str(tmp_path / "far" / "kernel.py"))
    with pytest.raises(ImportError, match=r"DOGMA_SERVICE_ROOT"):
        kernel.dogma_service_root()


def test_installed_distribution_resolves_service(kernel, tmp_path, monkeypatch):
    """A non-editable dogma-local-service install is discovered from trusted
    distribution metadata without requiring a checkout-specific env var."""
    site_packages = tmp_path / "venv" / "site-packages"
    package = site_packages / "dogma_service"
    package.mkdir(parents=True)
    (package / "method_guardrails.py").write_text("")
    (package / "edge_evaluation_plan.py").write_text("")

    class FakeDistribution:
        metadata = {"Name": "dogma_local_service"}

        def locate_file(self, relative):
            return site_packages / relative

    seen = {}

    def fake_distributions(*, path):
        seen["path"] = path
        return (FakeDistribution(),)

    monkeypatch.delenv("DOGMA_SERVICE_ROOT", raising=False)
    monkeypatch.setattr(kernel, "__file__", str(tmp_path / "skill" / "kernel.py"))
    monkeypatch.syspath_prepend(str(site_packages))
    monkeypatch.setattr(importlib.metadata, "distributions", fake_distributions)

    assert kernel.dogma_service_root() == str(site_packages.resolve())
    assert str(site_packages.resolve()) in seen["path"]


def test_cwd_distribution_metadata_is_not_trusted(kernel, tmp_path, monkeypatch):
    """Even plausible distribution metadata on cwd's sys.path entry is user
    workspace content, not an installed dependency, and must be excluded."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_skill = tmp_path / "installed-skill" / "kernel.py"
    seen = {}

    def fake_distributions(*, path):
        seen["path"] = path
        return ()

    monkeypatch.delenv("DOGMA_SERVICE_ROOT", raising=False)
    monkeypatch.chdir(workspace)
    monkeypatch.syspath_prepend(str(workspace))
    monkeypatch.setattr(kernel, "__file__", str(outside_skill))
    monkeypatch.setattr(importlib.metadata, "distributions", fake_distributions)

    with pytest.raises(ImportError, match=r"DOGMA_SERVICE_ROOT"):
        kernel.dogma_service_root()
    assert str(workspace.resolve()) not in seen["path"]


def test_already_loaded_shadow_package_is_rejected(kernel, tmp_path, monkeypatch):
    """A workspace package imported before the skill cannot win through
    sys.modules after the resolver has selected the trusted Dogma service."""
    shadow = types.ModuleType("dogma_service")
    shadow.__file__ = str(tmp_path / "workspace" / "dogma_service" / "__init__.py")
    monkeypatch.setitem(sys.modules, "dogma_service", shadow)

    with pytest.raises(ImportError, match=r"already-loaded shadow module"):
        kernel.dogma_load_builders(service_root=str(REPO_ROOT))
