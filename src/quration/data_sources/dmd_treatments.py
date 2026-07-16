"""Vocabulary of approved / late-stage Duchenne Muscular Dystrophy (DMD) treatments.

This module is the single source of truth for which interventions count as "DMD
treatment" when searching for transcriptomic datasets with paired pre/post-treatment
muscle biopsies. Scope is intentionally limited to approved or late-stage clinical
agents (see ``DMD_TREATMENTS``), excluding purely preclinical / early-phase compounds.

Two consumers depend on this data:
  1. Query expansion — generic + brand + legacy aliases broaden GEO/ClinicalTrials.gov
     recall, since investigators deposit data under inconsistent names
     (e.g. "eteplirsen", "Exondys 51", and "AVI-4658" are the same drug).
  2. The LLM pairing second-pass — class/mechanism let the model reason about whether
     a sample's metadata describes a treatment arm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal

DMDTreatmentClass = Literal[
    "corticosteroid",
    "exon_skipping",
    "readthrough",
    "gene_therapy",
    "hdac_inhibitor",
]


@dataclass(frozen=True)
class DMDTreatment:
    """A single approved/late-stage DMD intervention and its search aliases."""

    generic_name: str
    drug_class: DMDTreatmentClass
    mechanism: str
    brand_names: List[str] = field(default_factory=list)
    # Legacy / development-code aliases seen in older depositions and publications.
    aliases: List[str] = field(default_factory=list)
    # Targeted exon for exon-skipping antisense oligonucleotides (None otherwise).
    target_exon: int | None = None

    def all_names(self) -> List[str]:
        """All searchable names for this treatment (generic + brand + aliases)."""
        return [self.generic_name, *self.brand_names, *self.aliases]


# Approved or late-stage DMD treatments. Sources: FDA approvals through 2024
# (Exondys 51 2016, Emflaza 2017, Vyondys 53 2019, Viltepso 2020, Amondys 45 2021,
# Agamree/vamorolone 2023, Elevidys 2023, Duvyzat/givinostat 2024) plus EMA-conditional
# Translarna (ataluren).
DMD_TREATMENTS: List[DMDTreatment] = [
    # --- Corticosteroids (standard of care) ---
    DMDTreatment(
        generic_name="prednisone",
        drug_class="corticosteroid",
        mechanism="glucocorticoid anti-inflammatory",
        brand_names=["Deltasone"],
    ),
    DMDTreatment(
        generic_name="prednisolone",
        drug_class="corticosteroid",
        mechanism="glucocorticoid anti-inflammatory",
    ),
    DMDTreatment(
        generic_name="deflazacort",
        drug_class="corticosteroid",
        mechanism="glucocorticoid anti-inflammatory",
        brand_names=["Emflaza", "Calcort"],
    ),
    DMDTreatment(
        generic_name="vamorolone",
        drug_class="corticosteroid",
        mechanism="dissociative steroid (membrane stabilizer)",
        brand_names=["Agamree"],
        aliases=["VBP15"],
    ),
    # --- Exon-skipping antisense oligonucleotides ---
    DMDTreatment(
        generic_name="eteplirsen",
        drug_class="exon_skipping",
        mechanism="phosphorodiamidate morpholino, exon 51 skipping",
        brand_names=["Exondys 51", "Exondys"],
        aliases=["AVI-4658"],
        target_exon=51,
    ),
    DMDTreatment(
        generic_name="golodirsen",
        drug_class="exon_skipping",
        mechanism="phosphorodiamidate morpholino, exon 53 skipping",
        brand_names=["Vyondys 53", "Vyondys"],
        aliases=["SRP-4053"],
        target_exon=53,
    ),
    DMDTreatment(
        generic_name="viltolarsen",
        drug_class="exon_skipping",
        mechanism="phosphorodiamidate morpholino, exon 53 skipping",
        brand_names=["Viltepso"],
        aliases=["NS-065", "NCNP-01"],
        target_exon=53,
    ),
    DMDTreatment(
        generic_name="casimersen",
        drug_class="exon_skipping",
        mechanism="phosphorodiamidate morpholino, exon 45 skipping",
        brand_names=["Amondys 45", "Amondys"],
        aliases=["SRP-4045"],
        target_exon=45,
    ),
    # --- Nonsense-mutation readthrough ---
    DMDTreatment(
        generic_name="ataluren",
        drug_class="readthrough",
        mechanism="nonsense mutation readthrough",
        brand_names=["Translarna"],
        aliases=["PTC124"],
    ),
    # --- Gene therapy ---
    DMDTreatment(
        generic_name="delandistrogene moxeparvovec",
        drug_class="gene_therapy",
        mechanism="AAV micro-dystrophin gene transfer",
        brand_names=["Elevidys"],
        aliases=["SRP-9001", "micro-dystrophin", "microdystrophin"],
    ),
    # --- HDAC inhibitor ---
    DMDTreatment(
        generic_name="givinostat",
        drug_class="hdac_inhibitor",
        mechanism="histone deacetylase inhibitor",
        brand_names=["Duvyzat"],
        aliases=["ITF2357"],
    ),
]


def all_treatment_names() -> List[str]:
    """Flat, de-duplicated list of every searchable treatment name (lowercased)."""
    names: list[str] = []
    for treatment in DMD_TREATMENTS:
        names.extend(name.lower() for name in treatment.all_names())
    # Preserve order while de-duplicating.
    return list(dict.fromkeys(names))


def treatments_by_class(drug_class: DMDTreatmentClass) -> List[DMDTreatment]:
    """All treatments in a given class."""
    return [t for t in DMD_TREATMENTS if t.drug_class == drug_class]
