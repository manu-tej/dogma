"""Heuristic detection of survival/clinical data in GEO datasets."""

import re
from typing import Any


def detect_survival_data(
    title: str | None = None,
    summary: str | None = None,
    overall_design: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Detect if a dataset likely contains survival/clinical outcome data.

    Uses heuristic keyword matching to identify datasets with:
    - Survival data (OS, PFS, DFS, etc.)
    - Clinical trial data
    - Patient outcome data

    Args:
        title: Dataset title
        summary: Dataset summary/description
        overall_design: Overall design description
        metadata: Additional metadata dictionary

    Returns:
        True if survival data likely present, False otherwise
    """
    # Combine all text fields for searching
    combined_text = " ".join(
        [
            title or "",
            summary or "",
            overall_design or "",
        ]
    ).lower()

    # Survival-related keywords
    survival_keywords = [
        "survival",
        "overall survival",
        "os ",
        " os,",
        "progression-free survival",
        "pfs ",
        " pfs,",
        "disease-free survival",
        "dfs ",
        " dfs,",
        "prognosis",
        "prognostic",
        "outcome",
        "relapse-free",
        "recurrence-free",
        "event-free survival",
        "time to progression",
        "ttp ",
        " ttp,",
        "hazard ratio",
        "kaplan-meier",
        "cox regression",
    ]

    # Check for survival keywords
    for keyword in survival_keywords:
        if keyword in combined_text:
            return True

    # Check for clinical trial indicators
    clinical_trial_patterns = [
        r"nct\d{8}",  # NCT IDs
        r"clinical trial",
        r"phase [i]{1,3} trial",
        r"phase [1-3] trial",
        r"randomized.*trial",
        r"multicenter.*trial",
    ]

    for pattern in clinical_trial_patterns:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return True

    # Check for terms that suggest clinical follow-up
    clinical_followup_keywords = [
        "follow-up",
        "followup",
        "followed for",  # e.g. "patients were followed for 5 years"
        "clinical data",
        "clinical annotation",
        "patient outcome",
        "treatment response",
        "therapeutic response",
    ]

    for keyword in clinical_followup_keywords:
        if keyword in combined_text:
            return True

    return False


def extract_survival_keywords(
    title: str | None = None,
    summary: str | None = None,
    overall_design: str | None = None,
) -> list[str]:
    """Extract specific survival-related keywords found in the text.

    Args:
        title: Dataset title
        summary: Dataset summary/description
        overall_design: Overall design description

    Returns:
        List of survival keywords found
    """
    combined_text = " ".join(
        [
            title or "",
            summary or "",
            overall_design or "",
        ]
    ).lower()

    found_keywords = []

    keywords_to_check = [
        "overall survival",
        "progression-free survival",
        "disease-free survival",
        "relapse-free survival",
        "event-free survival",
        "prognosis",
        "clinical outcome",
        "clinical trial",
        "follow-up",
        "treatment response",
    ]

    for keyword in keywords_to_check:
        if keyword in combined_text:
            found_keywords.append(keyword)

    # Check for NCT IDs. Match against the ORIGINAL-case text (combined_text is
    # lowercased) and normalize to upper so the canonical "NCT01234567" is surfaced.
    combined_raw = " ".join([title or "", summary or "", overall_design or ""])
    nct_matches = re.findall(r"nct\d{8}", combined_raw, re.IGNORECASE)
    if nct_matches:
        found_keywords.extend(f"NCT ID: {nct.upper()}" for nct in nct_matches[:3])

    return found_keywords


# Alias to match original spec function name
def detect_maybe_has_survival_data(
    title: str,
    summary: str,
    overall_design: str,
    primary_pmid: str | None,
    raw_metadata: dict[str, Any],
) -> bool:
    """
    Heuristic to detect if a dataset might have survival data.

    This function matches the original spec signature.

    Returns True if:
    - Any of 'survival', 'overall survival', 'progression-free survival',
      'prognosis' appears in title, summary, or design text (case-insensitive).
    - OR if there is a clear indication that the study is linked to a clinical trial
      (e.g., NCT IDs or 'clinical trial' mentioned).
    - Otherwise False.

    Args:
        title: Dataset title
        summary: Dataset summary
        overall_design: Overall design description
        primary_pmid: Primary PubMed ID (if available)
        raw_metadata: Raw metadata dictionary

    Returns:
        True if survival data might be present, False otherwise
    """
    return detect_survival_data(
        title=title,
        summary=summary,
        overall_design=overall_design,
        metadata=raw_metadata,
    )
