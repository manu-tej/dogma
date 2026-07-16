# src/quration/hypothesis/orchestrator/seed_derivation.py
"""Real query->seed derivation for the /start (KG-substrate) path.

`LlmSeedDeriver` turns a free-text query into UniProt accessions: the LLM names the
central gene/protein symbols, then `UniProtClient` maps each to a reviewed-human
accession. `LiveSeedSupervisor` swaps the demo's canned `seeds_for` for this while
keeping `LiveSupervisor`'s real `triage`/`propose_test`.
"""

import json
import logging

from quration.hypothesis.orchestrator.real_pipeline import LiveSupervisor
from quration.hypothesis.orchestrator.seeding import _strip_code_fences

logger = logging.getLogger(__name__)

_SEED_SYSTEM = (
    "You extract the central gene or protein symbols from a biological question, so we can "
    "find the causal PATH between them in a signaling network. Name AT LEAST TWO official "
    "HGNC gene symbols when the question implies a mechanism (the key target plus likely "
    "mediators/effectors), most central first, at most 6. Reply with ONLY a JSON array of "
    'symbols (strings), e.g. ["EGFR","KRAS","MAPK1"]. If none apply, reply [].'
)


def _first_json_array(text: str) -> str:
    """Best-effort extraction of a single JSON array from model output."""
    t = _strip_code_fences(text)
    try:
        json.loads(t)
        return t
    except json.JSONDecodeError:
        start, end = t.find("["), t.rfind("]")
        if start != -1 and end > start:
            return t[start : end + 1]
        return t


class LlmSeedDeriver:
    """Derives UniProt accession seeds from a query (LLM symbols -> UniProt mapping)."""

    def __init__(self, provider, model: str, uniprot, max_seeds: int = 6):
        self._provider = provider
        self._model = model
        self._uniprot = uniprot
        self._max_seeds = max_seeds

    def derive(self, query: str) -> list[str]:
        accessions: list[str] = []
        seen: set[str] = set()
        for symbol in self._extract_symbols(query)[: self._max_seeds]:
            accession = self._symbol_to_accession(symbol)
            if accession and accession not in seen:
                seen.add(accession)
                accessions.append(accession)
        return accessions

    def _extract_symbols(self, query: str) -> list[str]:
        try:
            raw = self._provider.create_message(
                messages=[{"role": "user", "content": query}],
                model=self._model,
                system=_SEED_SYSTEM,
                temperature=0.0,
            )
            data = json.loads(_first_json_array(raw))
            return [s.strip() for s in data if isinstance(s, str) and s.strip()]
        except Exception:
            logger.warning("seed symbol extraction failed for %r", query, exc_info=True)
            return []

    def _symbol_to_accession(self, symbol: str) -> str | None:
        try:
            hits = self._uniprot.search(
                f"gene_exact:{symbol} AND reviewed:true", organism="human", limit=1
            )
        except Exception:
            logger.warning("UniProt lookup failed for %r", symbol, exc_info=True)
            return None
        return hits[0].uniprot_id if hits else None


class LiveSeedSupervisor(LiveSupervisor):
    """`LiveSupervisor` whose `seeds_for` uses a real `LlmSeedDeriver`."""

    def __init__(self, deriver: LlmSeedDeriver):
        super().__init__()
        self._deriver = deriver

    def seeds_for(self, query: str) -> list[str]:
        return self._deriver.derive(query)
