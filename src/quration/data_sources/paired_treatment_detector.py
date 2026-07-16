"""Heuristic detection of paired pre/post-treatment muscle-biopsy designs.

This is the cheap first pass of the hybrid pairing strategy: it runs keyword
matching over dataset-level text (title/summary/overall-design) and, when available,
sample titles, to decide whether a GEO series *plausibly* contains muscle biopsies
collected from the same subjects before and after a treatment. Survivors of this
filter are then sent to the LLM second pass for confirmation.

Mirrors the structure of ``geo_survival_detector.py``. Three independent signals are
scored; a dataset is a candidate when it shows a biopsy signal AND a timepoint/pairing
signal (treatment context is a bonus that raises confidence but is not required, since
DMD natural-history biopsy series are also of interest as controls).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# --- Signal 1: muscle biopsy present -----------------------------------------
# Tissue/procedure terms that indicate a muscle biopsy was taken.
BIOPSY_KEYWORDS: List[str] = [
    "muscle biopsy",
    "muscle biopsies",
    "skeletal muscle",
    "needle biopsy",
    "open biopsy",
    "biceps brachii",
    "tibialis anterior",
    "gastrocnemius",
    "extensor digitorum brevis",
    "deltoid",
    "quadriceps",
    "vastus lateralis",
]

# --- Signal 2: pre/post timepoint or explicit pairing -------------------------
# Language indicating two timepoints around an intervention, or paired sampling.
PAIRING_KEYWORDS: List[str] = [
    "pre-treatment",
    "post-treatment",
    "pre treatment",
    "post treatment",
    "pre-dose",
    "post-dose",
    "before treatment",
    "after treatment",
    "before and after",
    "baseline",
    "follow-up biopsy",
    "follow up biopsy",
    "paired biopsy",
    "paired biopsies",
    "paired samples",
    "matched samples",
    "serial biopsy",
    "serial biopsies",
    "longitudinal",
    "pre- and post-",
    "pre/post",
]

# Regex signals for week/timepoint pairing (e.g. "week 24", "at 48 weeks", "month 12").
PAIRING_PATTERNS: List[str] = [
    r"\bweek\s*\d{1,3}\b",
    r"\b\d{1,3}\s*weeks?\b",
    r"\bmonth\s*\d{1,2}\b",
    r"\b\d{1,2}\s*months?\b",
    r"\btimepoint",
    r"\btime point",
    r"\bday\s*\d{1,3}\b",
]

# --- Signal 3: treatment context (confidence booster, not required) -----------
# Populated lazily from the DMD treatment vocabulary to avoid an import cycle at
# module import time.
def _treatment_keywords() -> List[str]:
    from quration.data_sources.dmd_treatments import all_treatment_names

    return all_treatment_names()


@dataclass
class PairingEvidence:
    """Structured result of the keyword pre-filter for one dataset."""

    has_biopsy_signal: bool
    has_pairing_signal: bool
    has_treatment_signal: bool
    biopsy_terms: List[str] = field(default_factory=list)
    pairing_terms: List[str] = field(default_factory=list)
    treatment_terms: List[str] = field(default_factory=list)

    @property
    def is_candidate(self) -> bool:
        """A dataset advances to the LLM second pass when it shows a biopsy AND a
        pre/post (or explicit pairing) signal."""
        return self.has_biopsy_signal and self.has_pairing_signal

    @property
    def confidence(self) -> str:
        """Coarse confidence label for ranking before the LLM pass."""
        if self.is_candidate and self.has_treatment_signal:
            return "high"
        if self.is_candidate:
            return "medium"
        return "low"


def _find_terms(text: str, keywords: List[str]) -> List[str]:
    """Return the subset of ``keywords`` present in ``text`` (already lowercased)."""
    return [kw for kw in keywords if kw in text]


def detect_paired_pre_post(
    title: Optional[str] = None,
    summary: Optional[str] = None,
    overall_design: Optional[str] = None,
    sample_titles: Optional[List[str]] = None,
    treatment_names: Optional[List[str]] = None,
) -> PairingEvidence:
    """Heuristically score a dataset for paired pre/post-treatment biopsy design.

    Args:
        title: Series title.
        summary: Series summary/abstract.
        overall_design: GEO "overall design" field — the richest source of timepoint
            language, since it describes the sampling scheme.
        sample_titles: Per-sample titles (e.g. "Patient 3 post-treatment"). When
            present these dramatically improve pairing detection, because pre/post
            structure is often only visible at the sample level.
        treatment_names: Drug names to treat as the treatment signal. Defaults to the
            DMD vocabulary; pass a disease profile's names for other conditions (or an
            empty list to disable the treatment signal).

    Returns:
        A ``PairingEvidence`` with per-signal booleans and the matched terms.
    """
    combined_text = " ".join(
        [
            title or "",
            summary or "",
            overall_design or "",
            " ".join(sample_titles or []),
        ]
    ).lower()

    treatment_vocab = (
        [t.lower() for t in treatment_names]
        if treatment_names is not None
        else _treatment_keywords()
    )

    biopsy_terms = _find_terms(combined_text, BIOPSY_KEYWORDS)
    pairing_terms = _find_terms(combined_text, PAIRING_KEYWORDS)
    treatment_terms = _find_terms(combined_text, treatment_vocab)

    # Regex-based timepoint signals augment the keyword pairing list.
    for pattern in PAIRING_PATTERNS:
        match = re.search(pattern, combined_text)
        if match:
            pairing_terms.append(match.group(0).strip())

    return PairingEvidence(
        has_biopsy_signal=bool(biopsy_terms),
        has_pairing_signal=bool(pairing_terms),
        has_treatment_signal=bool(treatment_terms),
        biopsy_terms=biopsy_terms,
        pairing_terms=list(dict.fromkeys(pairing_terms)),
        treatment_terms=treatment_terms,
    )
