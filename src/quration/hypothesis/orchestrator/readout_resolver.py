"""Agentic direct-or-best-proxy readout resolver.

Given the ideal readout and pre-fetched GEO+PRIDE candidates, pick the dataset that
best measures the claim and record the FACTUAL directness gap (direct vs proxy).
The LLM (Task 7) only ranks/judges; Python owns the search + the deterministic
fallback below. directness_for is the offline truth the LLM judgment must beat.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "You select the public dataset that best measures a biological claim's IDEAL "
    "readout. Prefer the dataset whose assay directly measures the claimed modality "
    "(e.g. phosphoproteomics for a phosphorylation claim) over an indirect proxy. "
    'Reply with ONLY a JSON object {"choice": <integer index>}. No prose.'
)


def _extract_json_object(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: t.rfind("```")]
        t = t.strip()
    try:
        json.loads(t)
        return t
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        return t[s : e + 1] if s != -1 and e > s else t

from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate
from quration.hypothesis.orchestrator.evaluation_plan import (
    Directness, Modality, ReadoutSpec, ResolvedReadout,
)

# Tokens that name a specific assay. Checked first, because they identify what the
# experiment actually measured.
_SPECIFIC_ASSAY_MODALITY: dict[str, Modality] = {
    "phosphoproteomics": "phospho", "phosphosite": "phospho", "phospho": "phospho",
    "bisulfite": "methylation", "methylation": "methylation", "methyl": "methylation",
    "chip-seq": "binding", "chip seq": "binding", "chip": "binding",
    "co-ip": "binding", "immunoprecipitation": "binding",
    "proteomics": "protein", "proteome": "protein", "proteom": "protein",
    "mass spec": "protein",
    "rna-seq": "transcript", "rna seq": "transcript", "scrna": "transcript",
    "microarray": "transcript", "transcriptom": "transcript",
}

# Tokens that describe an experiment's *aim* rather than its assay. "expression" is
# the offender: it appears in the title of proteomics, ChIP-seq and phospho studies
# alike, so it identifies nothing on its own.
_GENERIC_MODALITY: dict[str, Modality] = {
    "expression": "transcript",
    "interaction": "binding",
}


def _first_match(blob: str, table: dict[str, Modality]) -> Modality | None:
    for token, modality in table.items():
        if token in blob:
            return modality
    return None


def _candidate_modality(c: DatasetCandidate) -> Modality:
    """What modality a dataset actually measured.

    Two orderings matter, and neither was respected before.

    1. The structured `assay` field beats the free-text `title`. The title is prose;
       the assay field is the answer.
    2. A specific assay name beats a generic aim word.

    Previously this scanned one flat dict in insertion order over
    `assay + " " + title`, and "expression" was inserted before "phospho". So
    *"Phosphoproteomic profiling of expression changes"* classified as `transcript`
    — and so did a proteomics study and a ChIP-seq study whose titles mention
    expression, which is most of them. The consequence inverted the one guarantee
    this module exists to make: `directness_for("phospho", <a real phospho dataset>)`
    returned `proxy_modality`, i.e. the tool that refuses to let mRNA test a
    phosphorylation event was reporting a phospho assay as a stand-in for itself.
    """
    assay = (c.assay or "").lower()
    title = (c.title or "").lower()

    for blob in (assay, title):
        if not blob:
            continue
        specific = _first_match(blob, _SPECIFIC_ASSAY_MODALITY)
        if specific is not None:
            return specific

    # Only now fall back to aim words, and only from the assay field first.
    for blob in (assay, title):
        generic = _first_match(blob, _GENERIC_MODALITY)
        if generic is not None:
            return generic

    return "unknown"


def directness_for(ideal_modality: Modality, c: DatasetCandidate) -> Directness:
    """The FACTUAL gap between what the dataset measures and the ideal readout."""
    cm = _candidate_modality(c)
    if cm == ideal_modality:
        return "direct"
    if cm == "unknown":
        return "wrong_assay"
    # All remaining non-direct, non-unknown cross-modality pairs are a proxy
    # at this scope (e.g. mRNA for a phospho claim). Task 7's LLM judge refines.
    return "proxy_modality"


_RATIONALE = {
    "direct": "directly measures the claimed entity's modality",
    "proxy_modality": "different modality than the claim — a proxy (e.g. mRNA for a phospho claim)",
    "proxy_correlation": "stands in via correlation, not direct measurement",
    "wrong_assay": "the assay cannot measure the claimed entity",
    "not_evaluable": "no measurable readout for this claim",
}


class ResolveOutcome(BaseModel):
    resolved_readout: ResolvedReadout | None = None
    directness: Directness
    dataset: DatasetCandidate | None = None
    alternatives: list[DatasetCandidate] = Field(default_factory=list)
    proxy_rationale: str = ""
    resolver_provenance: dict = Field(default_factory=dict)


class ReadoutResolverService(Protocol):
    def resolve(self, ideal: ReadoutSpec, candidates: list[DatasetCandidate]) -> ResolveOutcome: ...


def _rank(ideal: ReadoutSpec, candidates: list[DatasetCandidate]) -> list[DatasetCandidate]:
    # direct beats proxy; within a tier, more match_reasons first.
    order = {"direct": 0, "proxy_modality": 1, "proxy_correlation": 2, "wrong_assay": 3, "not_evaluable": 4}
    return sorted(candidates,
                  key=lambda c: (order[directness_for(ideal.modality, c)], -len(c.match_reasons or [])))


def _outcome_for(ideal: ReadoutSpec, ranked: list[DatasetCandidate], provenance: dict) -> ResolveOutcome:
    if not ranked:
        return ResolveOutcome(directness="not_evaluable",
                              proxy_rationale="no public dataset found for this readout",
                              resolver_provenance=provenance)
    best = ranked[0]
    directness = directness_for(ideal.modality, best)
    return ResolveOutcome(
        resolved_readout=ResolvedReadout(
            measured_entity=ideal.claimed_entity, measured_modality=_candidate_modality(best),
            assay=best.assay or best.title, source=best.source, accession=best.accession),
        directness=directness, dataset=best, alternatives=ranked[1:],
        proxy_rationale=_RATIONALE[directness], resolver_provenance=provenance)


class RealReadoutResolver:
    """Python-orchestrated resolver. With provider=None it uses the deterministic
    ranking only; Task 7 layers an LLM re-rank on top with this as the fallback."""

    def __init__(self, provider=None, model: str = ""):  # "" = no LLM model; Task 7 passes the model id
        self._provider = provider
        self._model = model

    def resolve(self, ideal: ReadoutSpec, candidates: list[DatasetCandidate]) -> ResolveOutcome:
        ranked = _rank(ideal, candidates)
        queries = []
        if self._provider is not None and len(ranked) > 1:
            ranked, queries = self._llm_rerank(ideal, ranked)
        prov = {"model": self._model or None, "n_candidates": len(candidates),
                "sources_searched": sorted({c.source for c in candidates}),
                "queries_tried": queries}
        return _outcome_for(ideal, ranked, prov)

    def _llm_rerank(self, ideal: ReadoutSpec, ranked: list[DatasetCandidate]):
        lines = [f"Claim ideal readout: {ideal.claimed_entity} ({ideal.modality}, "
                 f"{ideal.ideal_assay_class})", ""]
        for i, c in enumerate(ranked):
            lines.append(f"[{i}] {c.source}:{c.accession} assay={c.assay} — {c.title}")
        try:
            raw = self._provider.create_message(
                messages=[{"role": "user", "content": "\n".join(lines)}],
                model=self._model, system=_JUDGE_SYSTEM, temperature=0.0)
            j = json.loads(_extract_json_object(raw)).get("choice")
            if isinstance(j, int) and 0 <= j < len(ranked):
                chosen = ranked[j]
                return [chosen, *[c for k, c in enumerate(ranked) if k != j]], ["\n".join(lines)]
        except Exception:
            logger.warning("readout LLM re-rank failed; using deterministic order", exc_info=True)
        return ranked, []


class DemoReadoutResolver:
    """Synthetic offline proxy used only to demonstrate the resolver contract."""

    def resolve(self, ideal: ReadoutSpec, candidates: list[DatasetCandidate]) -> ResolveOutcome:
        proxy = DatasetCandidate(
            source="geo",
            accession="GSE-DEMO",
            title="Synthetic transcriptomic proxy (not a GEO result)",
            assay="RNA-Seq",
            match_reasons=["synthetic demo; not returned by a live search"],
        )
        return _outcome_for(
            ideal,
            [proxy],
            {
                "model": "demo",
                "mode": "synthetic_demo",
                "is_live": False,
                "n_candidates": 1,
                "sources_searched": [],
            },
        )
