"""Free-text node-label normalization for grounding/resolution.

Polars-free so both the OptimusKG backend and the OLS-ontology backend can share
it. LLM-authored seed labels are descriptive ("<symbol> receptor kinase"),
parenthetical ("<class> inhibitor (e.g., <code>/<name>)"), abbreviated, or
composite ("survival / apoptosis evasion") — none of which is a database key.
"""

from __future__ import annotations

import re

from quration.hypothesis.graph import NodeType

_HEDGE = re.compile(r"^\s*(?:e\.?g\.?|i\.?e\.?|such as|including|like)\s*[:,]?\s*", re.I)
_SPLIT = r"\s*[\/,;]\s*|\s+or\s+|\s+and\s+"


def clean_label(label: str) -> str:
    """Normalize a free-text node label for matching: drop a trailing parenthetical."""
    return re.sub(r"\s*\(.*\)\s*$", "", label or "").strip()


# A phospho-protein readout (pAKT, p-ERK, phospho-AKT, pS6) names a protein in a
# phosphorylated STATE — it grounds to the base protein, not a phenotype/pathway.
# Lowercase 'p' only (so "PI3K"/"PROTEIN" don't misfire) and a >=2-char base (so
# "pH" and "p53"/"p38" — a digit after p — are left alone).
_PHOSPHO = re.compile(r"^(?:phospho-?|p-?)([A-Za-z][A-Za-z0-9]+(?:/[A-Za-z0-9]+)?)$")


def protein_base(label: str) -> str | None:
    """Base protein symbol for a phospho-readout label, else None.

    "pAKT" -> "AKT", "phospho-AKT" -> "AKT", "pS6" -> "S6", "pERK1/2" -> "ERK1/2".
    None for non-readouts: "AKT", "PI3K", "p53"/"p38" (digit after p), "pH".
    """
    m = _PHOSPHO.match((label or "").strip())
    return m.group(1) if m else None


# A phospho-site token: residue letter (Ser/Thr/Tyr) + position, e.g. "S473", "T308".
_RESIDUE = re.compile(r"\b([STY]\d+)\b")


def phospho_residues(label: str) -> list[str]:
    """Phospho-site residues named in a label, in appearance order, de-duplicated.

    "pAKT (phospho-AKT; S473/T308)" -> ["S473", "T308"]; "phospho-AKT" -> [].
    (Callers that know the base symbol drop any residue equal to it — see grounding.py —
    so a protein named like a site, e.g. "S6", is not mistaken for its own residue.)
    """
    seen: set[str] = set()
    out: list[str] = []
    for r in _RESIDUE.findall(label or ""):
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def candidate_labels(label: str, node_type: NodeType) -> list[str]:
    """Ordered, de-duplicated match candidates for a free-text node label, most
    specific first:

      1. the cleaned label (parenthetical stripped);
      2. each side of a '/'-composite in the cleaned label;
      3. specific names rescued from inside a parenthetical (split on
         '/', ',', ';', ' or ', ' and ');
      4. for non-compound nodes, the leading token as a likely symbol. Skipped
         for compounds so an inhibitor is never grounded to its target gene.
    """
    base = clean_label(label)
    cands: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = s.strip()
        if len(s) > 1 and s.lower() not in seen:
            seen.add(s.lower())
            cands.append(s)

    if base:
        add(base)
        if "/" in base:  # composite concept node, e.g. "survival / apoptosis evasion"
            for part in base.split("/"):
                add(part)
    for inner in re.findall(r"\(([^)]*)\)", label or ""):
        inner = _HEDGE.sub("", inner)
        for tok in re.split(_SPLIT, inner):
            add(tok)
    if node_type != NodeType.COMPOUND:
        toks = base.split()
        if len(toks) > 1 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-]*", toks[0]):
            add(toks[0])
    return cands
