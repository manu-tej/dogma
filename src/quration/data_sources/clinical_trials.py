"""ClinicalTrials.gov API v2 client, scoped to DMD biopsy-collecting trials.

Strategy: DMD treatment trials register their biopsy collection in the protocol, so
the trial registry is a higher-recall entry point than GEO free-text search. This
client finds interventional DMD trials that mention muscle biopsy, then exposes the
linked PubMed IDs — the bridge used to walk back to GEO depositions (NCT → PMID → GSE).

API reference: https://clinicaltrials.gov/data-api/api (v2, JSON).
Mirrors the rate-limiting / retry style of ``GEOFetcher``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://clinicaltrials.gov/api/v2"

# Only request the protocol modules we actually use, to keep payloads small.
_REQUESTED_FIELDS = ",".join(
    [
        "protocolSection.identificationModule",
        "protocolSection.statusModule",
        "protocolSection.designModule",
        "protocolSection.armsInterventionsModule",
        "protocolSection.descriptionModule",
        "protocolSection.conditionsModule",
        "protocolSection.referencesModule",
    ]
)


@dataclass
class ClinicalTrial:
    """A DMD clinical trial relevant to paired-biopsy dataset discovery."""

    nct_id: str
    title: str
    status: Optional[str]
    phases: List[str] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    mentions_biopsy: bool = False
    # PubMed IDs linked from the trial's references module — the bridge to GEO.
    pmids: List[str] = field(default_factory=list)
    brief_summary: str = ""


class ClinicalTrialsFetcher:
    """Searches ClinicalTrials.gov v2 for DMD trials that collect muscle biopsies."""

    def __init__(self, rate_limit_per_sec: float = 5.0):
        self.base_url = BASE_URL
        self._min_interval = 1.0 / rate_limit_per_sec
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self._rate_limit()
        response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_biopsy_trials(
        self,
        condition: str = "Duchenne Muscular Dystrophy",
        treatments: Optional[List[str]] = None,
        max_results: int = 100,
        require_biopsy: bool = True,
    ) -> List[ClinicalTrial]:
        """Find interventional trials for a condition, optionally narrowed to
        biopsy-collecting ones.

        Args:
            condition: ClinicalTrials.gov ``query.cond`` string (e.g. a disease name).
            treatments: Intervention names to OR together in the query. When None, the
                search is condition-only (all interventional trials).
            max_results: Cap on returned trials.
            require_biopsy: When True, only return trials whose text mentions a biopsy.

        Returns:
            List of ``ClinicalTrial`` records, biopsy-mentioning ones first.
        """
        params: dict[str, Any] = {
            "query.cond": condition,
            "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
            "fields": _REQUESTED_FIELDS,
            "pageSize": min(max_results, 100),
            "format": "json",
        }
        # "muscle biopsy" as a free-text term biases ranking toward biopsy trials;
        # we still verify per-trial below since query.term is a soft signal.
        if require_biopsy:
            params["query.term"] = "muscle biopsy"
        if treatments:
            params["query.intr"] = " OR ".join(treatments)

        trials: List[ClinicalTrial] = []
        next_page: Optional[str] = None

        while len(trials) < max_results:
            if next_page:
                params["pageToken"] = next_page
            data = self._get("studies", params)

            for study in data.get("studies", []):
                trial = self._parse_study(study)
                if trial is None:
                    continue
                if require_biopsy and not trial.mentions_biopsy:
                    continue
                trials.append(trial)
                if len(trials) >= max_results:
                    break

            next_page = data.get("nextPageToken")
            if not next_page:
                break

        # Biopsy-mentioning trials first, then by number of linked PMIDs (more = more
        # likely to have a deposited dataset to walk back to).
        trials.sort(key=lambda t: (t.mentions_biopsy, len(t.pmids)), reverse=True)
        return trials

    def _parse_study(self, study: dict[str, Any]) -> Optional[ClinicalTrial]:
        """Flatten one v2 study record into a ``ClinicalTrial``."""
        protocol = study.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        nct_id = ident.get("nctId")
        if not nct_id:
            return None

        status = protocol.get("statusModule", {}).get("overallStatus")
        design = protocol.get("designModule", {})
        phases = design.get("phases", []) or []

        interventions = [
            intr.get("name", "")
            for intr in protocol.get("armsInterventionsModule", {}).get("interventions", [])
            if intr.get("name")
        ]
        conditions = protocol.get("conditionsModule", {}).get("conditions", []) or []

        desc = protocol.get("descriptionModule", {})
        brief_summary = desc.get("briefSummary", "") or ""
        detailed = desc.get("detailedDescription", "") or ""

        references = protocol.get("referencesModule", {}).get("references", []) or []
        pmids = [ref["pmid"] for ref in references if ref.get("pmid")]

        # Biopsy is "mentioned" if it appears in any free-text field we fetched.
        haystack = " ".join(
            [
                ident.get("briefTitle", ""),
                ident.get("officialTitle", ""),
                brief_summary,
                detailed,
            ]
        ).lower()
        mentions_biopsy = "biopsy" in haystack or "biopsies" in haystack

        return ClinicalTrial(
            nct_id=nct_id,
            title=ident.get("briefTitle", "") or ident.get("officialTitle", ""),
            status=status,
            phases=phases,
            interventions=interventions,
            conditions=conditions,
            mentions_biopsy=mentions_biopsy,
            pmids=pmids,
            brief_summary=brief_summary,
        )
