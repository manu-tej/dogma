"""What a published task tells the model must be true of the source study.

The first honest `--published` run exposed two dishonesties in the tasks
themselves, both caught by the model rather than by us:

- The DEG tasks supplied gene lists with no significance at all, so the model
  (correctly) refused to call anything differentially expressed — and the
  scorer counted the refusal as failure. The genes *are* the studies' reported
  significant DEG sets; the input now attests that, names the DOI, and says
  plainly that the fold-change magnitudes are representative curated values,
  not measured table entries. Attestation, not fabrication: no invented
  per-gene p-values.

- The pathway tasks fabricated `p_value: 0.001` and called the pathway
  "<source> analysis". The model's output — "one nominally significant
  (p=0.001, uncorrected) KEGG enrichment hit... I cannot confirm this is
  hsa04064" — was calibrated refusal aimed at a number we invented. The task
  now says no enrichment statistics were computed and asks for tool-grounded
  characterisation of the curated set instead.

Every task also declares `limitations`: what its inputs genuinely do not
establish. That is what `LimitationRecognitionCalculator` scores against.
"""

import pytest

from quration.benchmarks.tasks.published_tasks import (
    get_all_published_tasks,
    get_published_pathway_tasks,
    published_brca_tcga,
    published_stemcell_pathway,
)


class TestNoFabricatedStatistics:
    def test_pathway_payload_carries_no_invented_p_value(self):
        """`p_value: 0.001` reached the model labelled as an enrichment
        result. Nothing in the payload may claim a statistic nobody computed."""
        payload = published_stemcell_pathway()._pathway_payload()
        for pathway in payload:
            assert "p_value" not in pathway

    def test_pathway_context_states_no_enrichment_was_run(self):
        context = published_stemcell_pathway()._experiment_context()
        assert "No enrichment statistics" in context

    def test_pathway_name_is_not_dressed_as_an_analysis(self):
        payload = published_stemcell_pathway()._pathway_payload()
        assert all("analysis" not in p["name"] for p in payload)


class TestStudyAttestationIsExplicitAndSourced:
    def test_deg_context_names_the_doi(self):
        context = published_brca_tcga()._study_attestation()
        assert "10.1038/nature11412" in context

    def test_deg_context_attests_study_reported_significance(self):
        context = published_brca_tcga()._study_attestation()
        assert "significantly differentially expressed" in context

    def test_deg_context_says_magnitudes_are_representative(self):
        """The one thing the input must NOT let the model believe: that the
        log2FC numbers are measured table entries."""
        context = published_brca_tcga()._study_attestation()
        assert "representative" in context
        assert "not verbatim" in context or "not measured" in context


class TestEveryTaskDeclaresItsLimits:
    @pytest.mark.parametrize(
        "task", get_all_published_tasks(), ids=lambda t: t.task_id
    )
    def test_limitations_are_declared(self, task):
        limitations = task.get_expected_output().limitations
        assert limitations, f"{task.task_id} declares no input limitations"

    @pytest.mark.parametrize(
        "task", get_all_published_tasks(), ids=lambda t: t.task_id
    )
    def test_limitations_are_sentences_not_labels(self, task):
        for limitation in task.get_expected_output().limitations:
            assert len(limitation.split()) >= 5, limitation


class TestGeneSymbolsReachTheModel:
    """The 20260809_070936 run's pathway tasks ran blind. The payload carries
    the gene symbols, but `set_pathway_results` rendered `genes: {gene_count}`
    — the count, never the identities — so the model received "genes: 13",
    reported "the actual 13 gene symbols ... were not provided, only a count",
    and reconstructed the set from the paper title. The benchmark scored a
    model that never saw its input. The model caught this, not us.
    """

    @pytest.mark.parametrize(
        "task", get_published_pathway_tasks(), ids=lambda t: t.task_id
    )
    def test_every_gene_symbol_is_in_the_rendered_prompt(self, task):
        from quration.interpretation.prompts import PromptBuilder

        builder = PromptBuilder("pathway_enrichment")
        builder.set_pathway_results(task._pathway_payload())
        builder.set_variables(experiment_context=task._experiment_context())
        builder.set_variables(gene_set_size=str(len(task._gene_list)))
        _, user = builder.build()
        for gene in task._gene_list:
            assert gene in user, (
                f"{task.task_id}: {gene} is in the payload but never "
                f"reached the prompt"
            )

    def test_long_gene_lists_truncate_loudly_not_silently(self):
        """A cap on rendered genes is fine; a silent one is how this bug
        happened. Whatever is held back must be announced in the prompt."""
        from quration.interpretation.prompts import PromptBuilder

        genes = [f"GENE{i}" for i in range(60)]
        builder = PromptBuilder("pathway_enrichment")
        builder.set_pathway_results([{"name": "big set", "genes": genes}])
        builder.set_variables(experiment_context="x")
        _, user = builder.build()
        rendered = [g for g in genes if g in user]
        hidden = len(genes) - len(rendered)
        if hidden:
            assert f"+{hidden} more" in user


class TestTheHarnessScoresLimitationRecognition:
    def test_metrics_include_limitation_recognition_when_declared(self):
        from quration.benchmarks.harness import EvaluationHarness
        from quration.benchmarks.tasks.base import BenchmarkResult
        from quration.benchmarks.metrics import BenchmarkMetrics

        harness = EvaluationHarness()
        task = published_brca_tcga()
        result = BenchmarkResult(
            task_id=task.task_id,
            task_name=task.task_name,
            task_type=task.task_type,
            success=True,
            metrics=BenchmarkMetrics(),
            interpretation_summary=(
                "ESR1 is upregulated in luminal tumours. Note that per-gene "
                "adjusted p-values were not provided, and the fold-change "
                "magnitudes are representative values rather than measured "
                "table entries."
            ),
            claims_extracted=["ESR1 is upregulated"],
        )
        metrics = harness._calculate_task_metrics(task, result)
        assert metrics.limitation_recognition is not None
        assert metrics.limitation_recognition.measured
