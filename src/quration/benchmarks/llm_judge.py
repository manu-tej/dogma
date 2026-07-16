"""LLM-as-judge evaluation for interpretation quality.

Instead of regex claim extraction + fuzzy string matching, this module
uses a separate LLM call to evaluate whether an interpretation is
biologically correct, complete, and free of false claims.

Usage:
    # Evaluate a single interpretation
    judge = LLMJudge()
    verdict = await judge.evaluate(interpretation_text, ground_truth)

    # Re-evaluate an existing benchmark results file
    results = await judge.evaluate_benchmark_file("benchmarks/results/benchmark_xxx.json")
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are a molecular biology and bioinformatics expert evaluating the quality of automated gene expression interpretations.

You will receive:
1. The INPUT data (gene expression changes, experimental context)
2. The INTERPRETATION produced by an AI system
3. The GROUND TRUTH — what the interpretation should have identified

Your job is to evaluate the interpretation on three dimensions. Be strict but fair. The interpretation doesn't need to use the exact same words as the ground truth — it needs to capture the same biology."""

JUDGE_EVALUATION_PROMPT = """## Input Data
{input_context}

## AI Interpretation
{interpretation}

## Ground Truth Claims
{ground_truth_claims}

## Ground Truth Expected Genes
{expected_genes}

## Ground Truth Expected Pathways
{expected_pathways}

---

Evaluate the interpretation and respond with ONLY a JSON object (no markdown, no commentary):

{{
  "correctness": {{
    "score": <1-5>,
    "rationale": "<Are the biological claims factually correct? Does the interpretation accurately describe the biology?>"
  }},
  "completeness": {{
    "score": <1-5>,
    "rationale": "<Does the interpretation cover all the key findings from the ground truth? What's missing?>",
    "claims_found": ["<list each ground truth claim and whether it was addressed>"],
    "claims_missing": ["<ground truth claims not addressed at all>"]
  }},
  "hallucinations": {{
    "score": <1-5>,
    "rationale": "<Does the interpretation make false or unsupported claims? Are there errors?>",
    "false_claims": ["<any specific false or misleading statements>"]
  }},
  "clinical_utility": {{
    "score": <1-5>,
    "rationale": "<Would this interpretation be useful to a researcher trying to understand their experiment? Is it actionable?>"
  }},
  "overall": {{
    "score": <1-5>,
    "rationale": "<Overall assessment. Would a bioinformatician trust this interpretation?>"
  }}
}}

Scoring rubric:
- 5: Excellent — expert-level, no significant issues
- 4: Good — captures the biology well, minor gaps
- 3: Adequate — gets the main point but misses important details or has minor errors
- 2: Poor — significant gaps or errors that would mislead the researcher
- 1: Failing — wrong, misleading, or useless"""


@dataclass
class JudgeVerdict:
    """Result of LLM judge evaluation for a single task."""

    task_id: str
    task_name: str
    correctness: float  # 1-5
    completeness: float  # 1-5
    hallucinations: float  # 1-5 (5 = no hallucinations)
    clinical_utility: float  # 1-5
    overall: float  # 1-5
    claims_found: list[str] = field(default_factory=list)
    claims_missing: list[str] = field(default_factory=list)
    false_claims: list[str] = field(default_factory=list)
    rationale: dict[str, str] = field(default_factory=dict)
    raw_response: str = ""

    @property
    def normalized_score(self) -> float:
        """Overall score normalized to 0-1."""
        return (self.overall - 1) / 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "scores": {
                "correctness": self.correctness,
                "completeness": self.completeness,
                "hallucinations": self.hallucinations,
                "clinical_utility": self.clinical_utility,
                "overall": self.overall,
            },
            "normalized_score": self.normalized_score,
            "claims_found": self.claims_found,
            "claims_missing": self.claims_missing,
            "false_claims": self.false_claims,
            "rationale": self.rationale,
        }


@dataclass
class JudgeBenchmarkReport:
    """Aggregated LLM judge results across all tasks."""

    run_id: str
    source_benchmark: str
    verdicts: list[JudgeVerdict] = field(default_factory=list)
    judge_model: str = ""

    @property
    def avg_correctness(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.correctness for v in self.verdicts) / len(self.verdicts)

    @property
    def avg_completeness(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.completeness for v in self.verdicts) / len(self.verdicts)

    @property
    def avg_hallucinations(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.hallucinations for v in self.verdicts) / len(self.verdicts)

    @property
    def avg_clinical_utility(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.clinical_utility for v in self.verdicts) / len(self.verdicts)

    @property
    def avg_overall(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.overall for v in self.verdicts) / len(self.verdicts)

    @property
    def normalized_score(self) -> float:
        """Overall score normalized to 0-1."""
        return (self.avg_overall - 1) / 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source_benchmark": self.source_benchmark,
            "judge_model": self.judge_model,
            "aggregate_scores": {
                "correctness": round(self.avg_correctness, 2),
                "completeness": round(self.avg_completeness, 2),
                "hallucinations": round(self.avg_hallucinations, 2),
                "clinical_utility": round(self.avg_clinical_utility, 2),
                "overall": round(self.avg_overall, 2),
                "normalized_score": round(self.normalized_score, 3),
            },
            "verdicts": [v.to_dict() for v in self.verdicts],
        }

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved judge report to {path}")

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("LLM JUDGE EVALUATION RESULTS")
        print("=" * 60)
        print(f"Source: {self.source_benchmark}")
        print(f"Judge model: {self.judge_model}")
        print(f"Tasks evaluated: {len(self.verdicts)}")
        print("-" * 60)
        print(f"{'Metric':<25} {'Score':>8} {'(out of 5)':>12}")
        print("-" * 60)
        print(f"{'Correctness':<25} {self.avg_correctness:>8.2f} {'':>12}")
        print(f"{'Completeness':<25} {self.avg_completeness:>8.2f} {'':>12}")
        print(f"{'No Hallucinations':<25} {self.avg_hallucinations:>8.2f} {'':>12}")
        print(f"{'Clinical Utility':<25} {self.avg_clinical_utility:>8.2f} {'':>12}")
        print(f"{'OVERALL':<25} {self.avg_overall:>8.2f} {'':>12}")
        print("-" * 60)
        print(f"{'Normalized (0-1)':<25} {self.normalized_score:>8.3f}")
        print("=" * 60)

        print("\nPer-task breakdown:")
        print(f"{'Task':<35} {'Corr':>5} {'Comp':>5} {'Hall':>5} {'Util':>5} {'Over':>5}")
        print("-" * 60)
        for v in self.verdicts:
            name = v.task_name[:33]
            print(
                f"{name:<35} {v.correctness:>5.1f} {v.completeness:>5.1f} "
                f"{v.hallucinations:>5.1f} {v.clinical_utility:>5.1f} {v.overall:>5.1f}"
            )

        # Show missed claims
        all_missing = []
        for v in self.verdicts:
            for claim in v.claims_missing:
                all_missing.append((v.task_name, claim))

        if all_missing:
            print(f"\nMissed claims ({len(all_missing)} total):")
            for task_name, claim in all_missing:
                print(f"  [{task_name[:20]}] {claim}")

        # Show false claims
        all_false = []
        for v in self.verdicts:
            for claim in v.false_claims:
                all_false.append((v.task_name, claim))

        if all_false:
            print(f"\nFalse claims ({len(all_false)} total):")
            for task_name, claim in all_false:
                print(f"  [{task_name[:20]}] {claim}")


# Ground truth data for each task (extracted from task definitions)
TASK_GROUND_TRUTH: dict[str, dict[str, Any]] = {
    "deg-synthetic-001": {
        "claims": [
            "TP53 is significantly upregulated",
            "p53 signaling pathway is activated",
            "Cell cycle arrest genes are induced",
            "Pro-apoptotic genes are upregulated",
            "Cell cycle progression genes are downregulated",
        ],
        "genes": ["TP53", "CDKN1A", "BAX", "MDM2", "CCND1", "MYC"],
        "pathways": ["p53 signaling", "Cell cycle", "Apoptosis"],
    },
    "deg-synthetic-002": {
        "claims": [
            "IL6 shows moderate upregulation",
            "Inflammatory response may be activated",
            "Signal is weak and should be interpreted with caution",
        ],
        "genes": ["IL6", "CXCL8", "TNF"],
        "pathways": ["Inflammatory response", "Cytokine signaling"],
    },
    "deg-synthetic-003": {
        "claims": [
            "No significant differential expression detected",
            "Changes are within normal variation",
            "Housekeeping genes show minimal changes",
        ],
        "genes": [],
        "pathways": [],
    },
    "deg-synthetic-004": {
        "claims": [
            "Strong interferon-gamma response detected",
            "Cytotoxic T cell activation markers elevated",
            "Pro-inflammatory cytokines upregulated",
            "Immunosuppressive genes downregulated",
            "Type 1 immune response activated",
        ],
        "genes": ["IFNG", "TNF", "CD8A", "GZMB", "STAT1"],
        "pathways": ["Interferon signaling", "T cell activation", "Cytokine signaling"],
    },
    "deg-synthetic-005": {
        "claims": [
            "E-cadherin downregulation indicates loss of epithelial phenotype",
            "Vimentin and fibronectin upregulation indicates mesenchymal transition",
            "EMT transcription factors SNAI1/ZEB1/TWIST1 are activated",
            "Classic epithelial-mesenchymal transition pattern detected",
        ],
        "genes": ["CDH1", "VIM", "SNAI1", "ZEB1", "CDH2"],
        "pathways": ["EMT", "Cell adhesion", "TGF-beta signaling"],
    },
    "batch-synthetic-001": {
        "claims": [
            "Batch effect is severely confounding",
            "Cannot separate batch from treatment effect",
            "Results will be uninterpretable",
            "Study design issue - recommend repeating with balanced design",
        ],
        "genes": [],
        "pathways": [],
    },
    "batch-synthetic-002": {
        "claims": [
            "Moderate batch effect detected",
            "Batch is not confounded with treatment",
            "Batch correction is recommended",
            "ComBat or similar methods should be effective",
        ],
        "genes": [],
        "pathways": [],
    },
    "batch-synthetic-003": {
        "claims": [
            "No significant batch effect detected",
            "Treatment effect is dominant",
            "Batch correction not necessary",
            "Data quality is good",
        ],
        "genes": [],
        "pathways": [],
    },
    "batch-synthetic-004": {
        "claims": [
            "Technical batch effect from sequencing depth",
            "Library size normalization required",
            "Treatment design is balanced",
            "TMM or RLE normalization recommended",
        ],
        "genes": [],
        "pathways": [],
    },
    "batch-synthetic-005": {
        "claims": [
            "Time-dependent batch effect detected",
            "Progressive drift in expression",
            "Treatment design is balanced across time",
            "Consider time as covariate in model",
        ],
        "genes": [],
        "pathways": [],
    },
    # --- New DEG edge cases ---
    "deg-synthetic-006": {
        "claims": [
            "AhR pathway activation by xenobiotic exposure",
            "CYP1A1/CYP1B1 induction indicates phase I detoxification",
            "NQO1 upregulation consistent with NRF2-mediated antioxidant response",
            "Xenobiotic metabolism activated",
            "Potential toxicological implications",
        ],
        "genes": ["CYP1A1", "CYP1B1", "AHR", "NQO1"],
        "pathways": ["Xenobiotic metabolism", "AhR signaling", "Drug metabolism - cytochrome P450"],
    },
    "deg-synthetic-007": {
        "claims": [
            "HIF-1alpha stabilization and activation",
            "VEGFA upregulation for angiogenesis",
            "Metabolic shift to glycolysis (LDHA/PDK1)",
            "Hypoxia-responsive genes activated",
            "VHL/EGLN1 oxygen sensing pathway disrupted",
        ],
        "genes": ["HIF1A", "VEGFA", "LDHA", "CA9", "PDK1"],
        "pathways": ["HIF-1 signaling", "Glycolysis", "Angiogenesis", "VEGF signaling"],
    },
    "deg-synthetic-008": {
        "claims": [
            "Competing oncogenic and tumor-suppressor signals",
            "MYC and TP53 co-upregulation is contradictory and unusual",
            "Loss of RB1/CDKN1A suggests cell cycle deregulation",
            "BCL2 upregulation with BAX downregulation favors survival",
            "Signal is complex and may reflect tumor heterogeneity",
        ],
        "genes": ["MYC", "TP53", "CCND1", "RB1", "PTEN", "BCL2"],
        "pathways": ["Cell cycle", "p53 signaling", "Apoptosis", "PI3K-AKT signaling"],
    },
    "deg-synthetic-009": {
        "claims": [
            "CDKN2A (p16) upregulation indicates cellular senescence",
            "SASP factors (IL6/CXCL8/MMP3) secreted",
            "LMNB1 loss is a senescence marker",
            "Proliferation markers suppressed (PCNA/MCM2)",
            "Telomerase (TERT) downregulation",
            "This is senescence not just cell cycle arrest",
        ],
        "genes": ["CDKN2A", "CDKN1A", "LMNB1", "IL6", "TERT"],
        "pathways": ["Cellular senescence", "SASP", "Cell cycle arrest", "p53/p21 pathway"],
    },
    # --- Pathway enrichment tasks ---
    "pathway-synthetic-001": {
        "claims": [
            "Apoptosis pathway activation",
            "p53-mediated cell death",
            "Caspase cascade engagement",
            "Drug-induced programmed cell death",
        ],
        "genes": [],
        "pathways": ["Apoptosis", "p53 signaling pathway", "Caspase cascade"],
    },
    "pathway-synthetic-002": {
        "claims": [
            "Interferon response activation",
            "TNF-mediated inflammation",
            "NF-kB pathway engagement",
            "Innate immune activation via TLR",
        ],
        "genes": [],
        "pathways": [
            "Interferon signaling",
            "TNF signaling",
            "NF-kappa B signaling",
            "Toll-like receptor signaling",
        ],
    },
    "pathway-synthetic-003": {
        "claims": [
            "Warburg effect / aerobic glycolysis",
            "HIF-1 driven metabolic adaptation",
            "AMPK energy sensing disruption",
            "Metabolic reprogramming in cancer",
        ],
        "genes": [],
        "pathways": ["Glycolysis", "HIF-1 signaling", "AMPK signaling"],
    },
    "pathway-synthetic-004": {
        "claims": [
            "Borderline statistical significance",
            "No strong pathway activation",
            "Results should be interpreted with caution",
            "May represent noise",
        ],
        "genes": [],
        "pathways": [],
    },
    "pathway-synthetic-005": {
        "claims": [
            "PI3K-AKT pathway activation",
            "MAPK/ERK cascade engagement",
            "mTOR pathway involvement",
            "RAS-driven signaling crosstalk",
            "Convergent oncogenic signaling",
        ],
        "genes": [],
        "pathways": ["PI3K-AKT signaling", "MAPK signaling", "mTOR signaling", "RAS signaling"],
    },
    # --- Gene function tasks ---
    "gf-synthetic-001": {
        "claims": [
            "TP53 is the guardian of the genome, controlling cell cycle and apoptosis",
            "RB1 encodes the retinoblastoma protein involved in cell cycle regulation",
            "PTEN negatively regulates the PI3K/AKT signaling pathway",
            "These genes cooperate in tumor suppression",
            "Loss-of-function mutations in these genes are common in cancer",
        ],
        "genes": ["TP53", "RB1", "PTEN"],
        "pathways": ["p53 signaling", "Cell cycle", "PI3K-AKT signaling"],
    },
    "gf-synthetic-002": {
        "claims": [
            "DNMT1 is a DNA methyltransferase responsible for maintenance methylation",
            "TET2 catalyzes DNA demethylation through conversion to 5-hydroxymethylcytosine",
            "EZH2 mediates polycomb repression via H3K27 trimethylation",
            "KDM5A is a histone demethylase targeting H3K4 methylation marks",
            "Epigenetic crosstalk among these regulators is disrupted in leukemia",
        ],
        "genes": ["DNMT1", "TET2", "EZH2", "KDM5A"],
        "pathways": ["DNA methylation", "Chromatin modification", "Polycomb repressive complex"],
    },
    "gf-synthetic-003": {
        "claims": [
            "SCN1A sodium channel mutations cause Dravet syndrome",
            "KCNQ2 potassium channel dysfunction leads to neonatal seizures",
            "CACNA1A calcium channel variants are linked to episodic ataxia and epilepsy",
            "Ion channel dysfunction disrupts neuronal excitability",
            "These genes have pharmacogenomic implications for antiepileptic drug selection",
        ],
        "genes": ["SCN1A", "KCNQ2", "CACNA1A"],
        "pathways": ["Ion channel transport", "Neuronal excitability", "Synaptic transmission"],
    },
    "gf-synthetic-004": {
        "claims": [
            "CYP2D6 polymorphisms significantly affect drug metabolism rates",
            "CYP3A4 is the major drug-metabolizing cytochrome P450 enzyme",
            "UGT1A1 catalyzes glucuronidation and variants cause Gilbert syndrome",
            "ABCB1 encodes P-glycoprotein, a major efflux transporter",
            "Pharmacogenomic variability in these genes drives inter-individual drug response differences",
        ],
        "genes": ["CYP2D6", "CYP3A4", "UGT1A1", "ABCB1"],
        "pathways": ["Drug metabolism - cytochrome P450", "Phase II conjugation", "ABC transporters"],
    },
    "gf-synthetic-005": {
        "claims": [
            "FOXP3 is the master regulator of regulatory T cell development",
            "FOXP3 is critical for maintaining immune tolerance",
            "Mutations in FOXP3 cause IPEX syndrome",
            "FOXP3 suppresses effector T cell activation",
            "FOXP3 is a therapeutic target in autoimmunity and cancer immunotherapy",
        ],
        "genes": ["FOXP3"],
        "pathways": ["T cell differentiation", "Immune regulation", "FOXP3 transcriptional network"],
    },
    # --- Published tasks ---
    "pub-deg-001": {
        "claims": [
            "ESR1 and estrogen receptor signaling upregulated in luminal tumors",
            "GATA3 and FOXA1 are key luminal transcription factors",
            "ERBB2 (HER2) shows elevated expression",
            "Basal-like markers KRT5/KRT14/KRT17 downregulated in luminal subtype",
            "Molecular subtypes show distinct expression patterns",
        ],
        "genes": ["ESR1", "GATA3", "FOXA1", "ERBB2", "KRT5", "KRT14"],
        "pathways": ["Estrogen receptor signaling", "Receptor tyrosine kinase signaling", "Cell differentiation"],
    },
    "pub-deg-002": {
        "claims": [
            "Strong interferon-stimulated gene (ISG) signature",
            "Type I interferon response is activated",
            "T cell markers are downregulated",
            "Lymphopenia indicated by reduced T cell gene expression",
            "Inflammatory monocyte signature present",
            "ISG15 and IFIT genes highly upregulated",
        ],
        "genes": ["ISG15", "IFIT1", "MX1", "OAS1", "CD3D", "CD8A"],
        "pathways": ["Type I interferon signaling", "Antiviral response", "Innate immune response", "T cell signaling"],
    },
    "pub-deg-003": {
        "claims": [
            "Collagen genes strongly upregulated indicating fibrosis",
            "Extracellular matrix remodeling signature",
            "MMP7 is a key IPF biomarker",
            "Surfactant proteins downregulated indicating AT2 cell dysfunction",
            "TGF-beta signaling activated",
            "Myofibroblast markers elevated",
        ],
        "genes": ["COL1A1", "MMP7", "FN1", "SFTPC", "TGFB1", "ACTA2"],
        "pathways": ["ECM organization", "TGF-beta signaling", "Collagen formation", "Wound healing"],
    },
    "pub-deg-004": {
        "claims": [
            "Astrocyte activation markers elevated with age",
            "Neuroinflammation indicated by GFAP and complement",
            "Synaptic genes downregulated",
            "BDNF reduction associated with cognitive decline",
            "Oxidative stress response genes upregulated",
        ],
        "genes": ["GFAP", "C3", "SYP", "BDNF", "CLU"],
        "pathways": ["Neuroinflammation", "Synaptic signaling", "Complement cascade", "Astrocyte activation"],
    },
    "pub-pathway-001": {
        "claims": [
            "Pluripotency transcription factors highly enriched",
            "OCT4-SOX2-NANOG core regulatory network",
            "Self-renewal pathways activated",
            "Epigenetic regulators present",
        ],
        "genes": [],
        "pathways": [
            "Signaling pathways regulating pluripotency",
            "Transcriptional regulation by OCT4",
            "POU5F1 (OCT4), SOX2, NANOG activate genes",
        ],
    },
    "pub-pathway-002": {
        "claims": [
            "NF-kB signaling pathway highly enriched",
            "Pro-inflammatory cytokines cluster together",
            "Cell survival genes present (BCL2, BIRC3)",
            "Adhesion molecules indicate inflammation",
        ],
        "genes": [],
        "pathways": [
            "NF-kappa B signaling pathway",
            "TNF signaling pathway",
            "Cytokine-cytokine receptor interaction",
            "IL-17 signaling pathway",
        ],
    },
}


class LLMJudge:
    """LLM-based evaluation of interpretation quality.

    Uses a separate LLM call to evaluate whether an interpretation
    correctly captures the biology, rather than regex + fuzzy matching.
    """

    def __init__(self, model: str = "claude-sonnet-4-5-20250929"):
        self._model = model
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            from quration.config import get_config

            llm_config = get_config().llm
            api_key = llm_config.anthropic.api_key
            self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()
        return self._client

    async def evaluate(
        self,
        task_id: str,
        task_name: str,
        interpretation: str,
        ground_truth: dict[str, Any],
        input_context: str = "",
    ) -> JudgeVerdict:
        """Evaluate a single interpretation using LLM judge.

        Args:
            task_id: Task identifier
            task_name: Human-readable task name
            interpretation: The AI-generated interpretation text
            ground_truth: Dict with 'claims', 'genes', 'pathways'
            input_context: Original input data description

        Returns:
            JudgeVerdict with scores and reasoning
        """
        client = await self._get_client()

        claims_text = "\n".join(f"- {c}" for c in ground_truth.get("claims", []))
        genes_text = ", ".join(ground_truth.get("genes", [])) or "None specified"
        pathways_text = ", ".join(ground_truth.get("pathways", [])) or "None specified"

        prompt = JUDGE_EVALUATION_PROMPT.format(
            input_context=input_context or "Not provided — evaluate based on interpretation content.",
            interpretation=interpretation,
            ground_truth_claims=claims_text,
            expected_genes=genes_text,
            expected_pathways=pathways_text,
        )

        response = await client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            json_text = raw_text
            if json_text.startswith("```"):
                json_text = json_text.split("\n", 1)[1]
                json_text = json_text.rsplit("```", 1)[0]
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse judge response for {task_id}: {raw_text[:200]}")
            return JudgeVerdict(
                task_id=task_id,
                task_name=task_name,
                correctness=0,
                completeness=0,
                hallucinations=0,
                clinical_utility=0,
                overall=0,
                raw_response=raw_text,
                rationale={"error": f"Failed to parse: {raw_text[:500]}"},
            )

        return JudgeVerdict(
            task_id=task_id,
            task_name=task_name,
            correctness=parsed.get("correctness", {}).get("score", 0),
            completeness=parsed.get("completeness", {}).get("score", 0),
            hallucinations=parsed.get("hallucinations", {}).get("score", 0),
            clinical_utility=parsed.get("clinical_utility", {}).get("score", 0),
            overall=parsed.get("overall", {}).get("score", 0),
            claims_found=parsed.get("completeness", {}).get("claims_found", []),
            claims_missing=parsed.get("completeness", {}).get("claims_missing", []),
            false_claims=parsed.get("hallucinations", {}).get("false_claims", []),
            rationale={
                k: parsed.get(k, {}).get("rationale", "")
                for k in ["correctness", "completeness", "hallucinations", "clinical_utility", "overall"]
            },
            raw_response=raw_text,
        )

    async def evaluate_benchmark_file(
        self,
        benchmark_path: str | Path,
    ) -> JudgeBenchmarkReport:
        """Re-evaluate an existing benchmark results file using LLM judge.

        This is zero-cost for interpretation (no re-running tasks).
        Only cost is the judge LLM calls (~10 short calls).

        Args:
            benchmark_path: Path to benchmark JSON results file

        Returns:
            JudgeBenchmarkReport with all verdicts
        """
        benchmark_path = Path(benchmark_path)

        with open(benchmark_path) as f:
            benchmark_data = json.load(f)

        run_id = benchmark_data["run_id"]
        results = benchmark_data["results"]

        logger.info(f"Evaluating {len(results)} tasks from benchmark {run_id}")

        verdicts = []
        for task_result in results:
            task_id = task_result["task_id"]
            task_name = task_result["task_name"]
            interpretation = task_result.get("interpretation_summary", "")

            if not interpretation:
                logger.warning(f"No interpretation for {task_id}, skipping")
                continue

            ground_truth = TASK_GROUND_TRUTH.get(task_id)
            if not ground_truth:
                logger.warning(f"No ground truth for {task_id}, skipping")
                continue

            logger.info(f"Judging {task_id}: {task_name}")

            verdict = await self.evaluate(
                task_id=task_id,
                task_name=task_name,
                interpretation=interpretation,
                ground_truth=ground_truth,
            )
            verdicts.append(verdict)

        report = JudgeBenchmarkReport(
            run_id=f"judge_{run_id}",
            source_benchmark=str(benchmark_path),
            verdicts=verdicts,
            judge_model=self._model,
        )

        # Auto-save next to the source benchmark
        judge_path = benchmark_path.parent / f"judge_{benchmark_path.name}"
        report.save(judge_path)
        report.print_summary()

        return report


async def main():
    """CLI entry point for running LLM judge evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Run LLM-as-judge evaluation on benchmark results")
    parser.add_argument(
        "benchmark_file",
        help="Path to benchmark results JSON file",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5-20250929",
        help="Model to use as judge (default: claude-sonnet-4-5-20250929)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    judge = LLMJudge(model=args.model)
    report = await judge.evaluate_benchmark_file(args.benchmark_file)

    print(f"\nNormalized score: {report.normalized_score:.1%}")
    print(f"Results saved to: benchmarks/results/judge_{Path(args.benchmark_file).name}")


if __name__ == "__main__":
    asyncio.run(main())
