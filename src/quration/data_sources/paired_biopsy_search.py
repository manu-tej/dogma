"""Find human transcriptomic datasets with paired pre/post-treatment muscle biopsies.

Disease-parameterized (see ``disease_profiles``); built for the DMD scoping review but
reusable for any condition. This orchestrator sits on top of the canonical GEO search
layer rather than duplicating it:

  - Discovery uses ``search_geo(QuerySpec)`` (shared query generation + GeoDatasetCandidate).
  - The trial bridge reads each candidate's ``primary_pmid`` (already extracted by
    search_geo from the esummary ``PubMedIds`` field) and matches it against the PMIDs
    cited by ClinicalTrials.gov biopsy trials — no fragile forward ELink, no SOFT parsing.
  - ``PairedBiopsyCandidate`` is a thin wrapper that annotates a ``GeoDatasetCandidate``
    with pairing evidence + trial provenance, so API/streaming consumers of the canonical
    model are unaffected.

Two-phase filtering keeps it cheap: screen series text first (title/summary/design), and
only fetch per-sample records for survivors. Survey mode relaxes the gate to enumerate the
landscape with a biopsy/pairing/treatment signal matrix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from quration.data_sources.clinical_trials import ClinicalTrial, ClinicalTrialsFetcher
from quration.data_sources.disease_profiles import DMD_PROFILE, DiseaseProfile
from quration.data_sources.geo import GEOFetcher
from quration.data_sources.geo_search import search_geo
from quration.data_sources.paired_treatment_detector import (
    PairingEvidence,
    detect_paired_pre_post,
)
from quration.models.geo_search import GeoDatasetCandidate, QuerySpec

_HUMAN_ORGANISM = "homo sapiens"

# Callable shape of search_geo, so tests can inject a fake discovery function.
SearchFn = Callable[..., List[GeoDatasetCandidate]]

_LLM_SYSTEM_PROMPT = """You are a bioinformatics curator screening GEO datasets for a \
scoping review of paired pre/post-treatment muscle biopsies. You decide whether a dataset \
contains PAIRED pre-treatment and post-treatment human skeletal-muscle biopsies for an \
approved or late-stage drug. Be conservative: distinguish patient muscle biopsies from \
in-vitro cell/organoid models, and the disease from a same-named gene. Respond with JSON \
only."""


@dataclass
class PairedBiopsyCandidate:
    """A ``GeoDatasetCandidate`` annotated with pairing evidence and trial provenance."""

    candidate: GeoDatasetCandidate
    pairing_evidence: PairingEvidence
    source: str  # "geo_direct", "trial_xref", or "both"
    linked_trials: List[str] = field(default_factory=list)
    linked_pmids: List[str] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    llm_verdict: Optional[Dict[str, Any]] = None

    # -- proxies onto the wrapped canonical model --
    @property
    def gse_id(self) -> str:
        return self.candidate.gse_id

    @property
    def title(self) -> str:
        return self.candidate.title

    @property
    def organism(self) -> Optional[str]:
        return self.candidate.organism

    @property
    def n_samples(self) -> Optional[int]:
        return self.candidate.n_samples

    @property
    def geo_url(self) -> str:
        return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={self.gse_id}"

    @property
    def rank_key(self) -> tuple:
        llm_ok = bool(self.llm_verdict and self.llm_verdict.get("is_paired_pre_post"))
        llm_conf = float(self.llm_verdict.get("confidence", 0.0)) if self.llm_verdict else 0.0
        conf_rank = {"high": 2, "medium": 1, "low": 0}[self.pairing_evidence.confidence]
        return (llm_ok, self.source == "both", bool(self.linked_trials), conf_rank, llm_conf)


class PairedBiopsySearch:
    """Find human datasets with paired pre/post-treatment muscle biopsies for a disease."""

    def __init__(
        self,
        search_fn: SearchFn = search_geo,
        geo_fetcher: Optional[GEOFetcher] = None,
        ct_fetcher: Optional[ClinicalTrialsFetcher] = None,
        llm_client: Any = None,
        model: Optional[str] = None,
        profile: DiseaseProfile = DMD_PROFILE,
    ):
        self.search_fn = search_fn
        self.geo = geo_fetcher or GEOFetcher()
        self.ct = ct_fetcher or ClinicalTrialsFetcher()
        self.llm_client = llm_client
        self.model = model
        self.profile = profile

    def _build_query_spec(self, survey: bool) -> QuerySpec:
        """Map the disease profile onto the canonical QuerySpec.

        Biopsy/muscle keywords always constrain the search. In precision mode the
        treatment vocabulary is added as keywords too; survey mode omits it to sweep
        the landscape.
        """
        keywords = ["muscle biopsy", "biopsy", "muscle"]
        if not survey and self.profile.treatment_names:
            keywords = keywords + list(self.profile.treatment_names)
        return QuerySpec(
            disease_terms=list(self.profile.geo_terms),
            therapy_class=None,
            therapy_scope="broad",
            targets_or_genes=[],
            study_keywords=keywords,
            must_have_clinical=False,
            min_samples=None,
        )

    def _pmid_to_trials(self, trials: List[ClinicalTrial]) -> Dict[str, List[str]]:
        pmid_map: Dict[str, List[str]] = {}
        for trial in trials:
            for pmid in trial.pmids:
                pmid_map.setdefault(pmid, []).append(trial.nct_id)
        return pmid_map

    def _candidate_pmids(self, gc: GeoDatasetCandidate) -> List[str]:
        """All PubMed IDs for a candidate (primary + any in raw esummary metadata)."""
        pmids: List[str] = []
        if gc.primary_pmid:
            pmids.append(str(gc.primary_pmid))
        raw = gc.raw_metadata or {}
        if isinstance(raw, dict):
            pm = raw.get("PubMedIds")
            if isinstance(pm, list):
                pmids.extend(str(p) for p in pm if p)
            elif pm:
                pmids.append(str(pm))
        return list(dict.fromkeys(pmids))

    def _sample_titles(self, gc: GeoDatasetCandidate) -> List[str]:
        """Sample titles for pairing detection — from the candidate if already fetched,
        otherwise via a bounded per-GSM fetch (the expensive phase-2 step)."""
        if gc.samples:
            return [s.title for s in gc.samples if s.title]
        try:
            return [
                s.get("title", "")
                for s in self.geo.fetch_gse_samples(gc.gse_id, limit=40)
            ]
        except Exception:
            return []

    def _screen(
        self,
        gc: GeoDatasetCandidate,
        survey: bool,
        pmid_to_trials: Dict[str, List[str]],
        nct_to_intr: Dict[str, List[str]],
    ) -> Optional[PairedBiopsyCandidate]:
        # Human-only gate (unknown organism is left for the LLM pass to judge).
        if gc.organism and _HUMAN_ORGANISM not in gc.organism.lower():
            return None

        design_notes = gc.experimental_design.notes if gc.experimental_design else ""
        tx_names = self.profile.treatment_names or None

        # Trial linkage via the candidate's own PubMed id(s).
        linked_trials: List[str] = []
        linked_pmids: List[str] = []
        for pmid in self._candidate_pmids(gc):
            if pmid in pmid_to_trials:
                linked_pmids.append(pmid)
                linked_trials.extend(pmid_to_trials[pmid])
        trial_linked = bool(linked_trials)

        # Phase 1 — series-level screen (no per-sample fetch).
        series_evidence = detect_paired_pre_post(
            title=gc.title,
            summary=gc.summary,
            overall_design=design_notes,
            treatment_names=tx_names,
        )
        if not series_evidence.has_biopsy_signal:
            return None
        if not survey and not (series_evidence.has_treatment_signal or trial_linked):
            return None

        # Phase 2 — fetch samples only for promising datasets, then require pairing.
        promising = (
            series_evidence.has_pairing_signal
            or series_evidence.has_treatment_signal
            or trial_linked
        )
        sample_titles = [] if (survey and not promising) else self._sample_titles(gc)
        evidence = detect_paired_pre_post(
            title=gc.title,
            summary=gc.summary,
            overall_design=design_notes,
            sample_titles=sample_titles,
            treatment_names=tx_names,
        )
        if not survey and not evidence.has_pairing_signal:
            return None

        from_direct = True  # everything reaching here came from the GEO search
        source = "both" if trial_linked else "geo_direct"

        interventions: List[str] = []
        for nct in linked_trials:
            interventions.extend(nct_to_intr.get(nct, []))

        return PairedBiopsyCandidate(
            candidate=gc,
            pairing_evidence=evidence,
            source=source,
            linked_trials=sorted(set(linked_trials)),
            linked_pmids=sorted(set(linked_pmids)),
            interventions=list(dict.fromkeys(interventions)),
        )

    def _llm_confirm(self, c: PairedBiopsyCandidate) -> None:
        if self.llm_client is None:
            return
        prompt = (
            f"GSE: {c.gse_id}\nTitle: {c.title}\nOrganism: {c.organism}\n"
            f"Sample count: {c.n_samples}\nSummary: {c.candidate.summary[:3000]}\n"
            f"Keyword evidence: biopsy={c.pairing_evidence.biopsy_terms}, "
            f"pairing={c.pairing_evidence.pairing_terms}, "
            f"treatment={c.pairing_evidence.treatment_terms}\n"
            f"Linked trials: {c.linked_trials}\n\n"
            'Return JSON: {"is_paired_pre_post": bool, "is_patient_biopsy": bool, '
            '"has_treatment": bool, "treatment_name": str|null, "timepoints": [str], '
            '"confidence": float, "rationale": str}'
        )
        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=600,
                system=[{"type": "text", "text": _LLM_SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            c.llm_verdict = json.loads(text)
        except Exception as e:
            c.llm_verdict = {"error": str(e)}

    def run(
        self,
        max_geo: int = 40,
        max_trials: int = 50,
        use_llm: bool = True,
        survey: bool = False,
    ) -> List[PairedBiopsyCandidate]:
        """Execute the pipeline and return ranked candidates."""
        trials = self.ct.search_biopsy_trials(
            condition=self.profile.ct_condition,
            treatments=self.profile.treatment_names or None,
            max_results=max_trials,
            require_biopsy=True,
        )
        pmid_to_trials = self._pmid_to_trials(trials)
        nct_to_intr = {t.nct_id: t.interventions for t in trials}

        spec = self._build_query_spec(survey)
        geo_candidates = self.search_fn(
            spec, max_results=max_geo, fetch_samples=False, parse_design=False
        )

        results: List[PairedBiopsyCandidate] = []
        for gc in geo_candidates:
            try:
                screened = self._screen(gc, survey, pmid_to_trials, nct_to_intr)
            except Exception as e:
                print(f"Error screening {getattr(gc, 'gse_id', '?')}: {e}")
                continue
            if screened is not None:
                results.append(screened)

        if use_llm and self.llm_client is not None:
            for c in results:
                self._llm_confirm(c)

        results.sort(key=lambda c: c.rank_key, reverse=True)
        return results


def to_markdown(candidates: List[PairedBiopsyCandidate]) -> str:
    """Render a ranked Markdown shortlist with a biopsy/pairing/treatment signal matrix."""
    if not candidates:
        return "# Paired pre/post-treatment biopsy datasets\n\n_No candidates found._\n"

    lines = [
        "# Paired pre/post-treatment biopsy datasets",
        "",
        f"{len(candidates)} candidate dataset(s), ranked by evidence strength.",
        "",
        "| Rank | GSE | Samples | Signals (B/P/Tx) | Source | Interventions | Pairing evidence | LLM | Trials |",
        "|------|-----|---------|------------------|--------|---------------|------------------|-----|--------|",
    ]
    for i, c in enumerate(candidates, 1):
        llm = c.llm_verdict or {}
        llm_cell = (
            f"{'✅' if llm.get('is_paired_pre_post') else '❌'} ({llm.get('confidence', '—')})"
            if c.llm_verdict and "error" not in c.llm_verdict
            else "—"
        )
        ev = c.pairing_evidence
        signals = (
            f"{'🅑' if ev.has_biopsy_signal else '·'}"
            f"{'🅟' if ev.has_pairing_signal else '·'}"
            f"{'🅣' if ev.has_treatment_signal else '·'}"
        )
        pairing = ", ".join(ev.pairing_terms[:4]) or "—"
        intr = ", ".join(c.interventions[:3]) or "—"
        trials = ", ".join(c.linked_trials[:2]) or "—"
        lines.append(
            f"| {i} | [{c.gse_id}]({c.geo_url}) | {c.n_samples or '?'} | {signals} | {c.source} | "
            f"{intr} | {pairing} | {llm_cell} | {trials} |"
        )
    lines.append("")
    lines.append("_Signals: 🅑 biopsy/muscle · 🅟 pre/post pairing · 🅣 treatment._")

    lines.extend(["", "## Details", ""])
    for i, c in enumerate(candidates, 1):
        lines.append(f"### {i}. {c.gse_id} — {c.title}")
        lines.append(f"- **Link:** {c.geo_url}")
        lines.append(f"- **Organism:** {c.organism or 'unknown'} | **Samples:** {c.n_samples or '?'}")
        lines.append(f"- **Source:** {c.source} | **Confidence:** {c.pairing_evidence.confidence}")
        if c.linked_trials:
            lines.append(f"- **Trials:** {', '.join(c.linked_trials)} | **PMIDs:** {', '.join(c.linked_pmids)}")
        if c.interventions:
            lines.append(f"- **Interventions:** {', '.join(c.interventions)}")
        if c.llm_verdict and "error" not in c.llm_verdict:
            v = c.llm_verdict
            lines.append(
                f"- **LLM:** paired={v.get('is_paired_pre_post')}, "
                f"patient_biopsy={v.get('is_patient_biopsy')}, treatment={v.get('treatment_name')}, "
                f"timepoints={v.get('timepoints')}, confidence={v.get('confidence')}"
            )
            if v.get("rationale"):
                lines.append(f"  - _{v['rationale']}_")
        lines.append("")

    return "\n".join(lines)
