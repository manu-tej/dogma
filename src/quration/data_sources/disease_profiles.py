"""Disease profiles for the paired pre/post-treatment biopsy discovery pipeline.

A ``DiseaseProfile`` parameterizes the three disease-specific inputs the pipeline
needs, so the same orchestrator works for any condition:
  - ``ct_condition``  : the ClinicalTrials.gov ``query.cond`` string.
  - ``geo_terms``     : disease synonyms OR-ed into the GEO search query.
  - ``treatment_names``: drug names for query expansion and the treatment signal.

The DMD profile is the rich default (tightened to Duchenne-specific terms so it does
not pull in FSHD/LGMD/myotonic/dermatomyositis). Unknown diseases get a generic
profile with no treatment vocabulary — survey mode still works; precision mode will
warn that without treatments it cannot enforce the treatment gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from quration.data_sources.dmd_treatments import all_treatment_names


@dataclass(frozen=True)
class DiseaseProfile:
    name: str
    ct_condition: str
    geo_terms: List[str]
    treatment_names: List[str] = field(default_factory=list)

    @property
    def has_treatments(self) -> bool:
        return bool(self.treatment_names)


# Duchenne-specific terms only — deliberately excludes the generic "muscular
# dystrophy" to keep other dystrophies out of a DMD-scoped search.
DMD_PROFILE = DiseaseProfile(
    name="dmd",
    ct_condition="Duchenne Muscular Dystrophy",
    geo_terms=["Duchenne", "DMD", "dystrophin"],
    treatment_names=all_treatment_names(),
)

_REGISTRY: Dict[str, DiseaseProfile] = {DMD_PROFILE.name: DMD_PROFILE}


def get_profile(disease: str) -> DiseaseProfile:
    """Resolve a disease name to a profile.

    Known names (e.g. "dmd") return the curated profile. Anything else returns a
    generic profile built from the raw string — usable for survey-mode landscape
    sweeps of arbitrary conditions.
    """
    key = disease.strip().lower()
    if key in _REGISTRY:
        return _REGISTRY[key]
    return DiseaseProfile(
        name=key,
        ct_condition=disease.strip(),
        geo_terms=[disease.strip()],
        treatment_names=[],
    )
