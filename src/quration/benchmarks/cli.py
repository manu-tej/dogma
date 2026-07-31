"""Benchmark CLI runner.

Command-line interface for running interpretation benchmarks.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from quration.benchmarks.harness import EvaluationHarness, HarnessConfig
from quration.benchmarks.tasks import (
    get_all_batch_tasks,
    get_all_deg_tasks,
    get_all_gene_function_tasks,
    get_all_pathway_tasks,
    get_all_published_tasks,
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration.

    Args:
        verbose: Enable debug logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def get_parser() -> argparse.ArgumentParser:
    """Create argument parser.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Run interpretation benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all synthetic benchmarks
  python -m quration.benchmarks.cli --synthetic

  # Run published paper benchmarks
  python -m quration.benchmarks.cli --published

  # Run specific task types
  python -m quration.benchmarks.cli --types deg batch

  # Run with specific tags
  python -m quration.benchmarks.cli --tags p53 immune

  # Run in parallel
  python -m quration.benchmarks.cli --parallel 3

  # Compare models
  python -m quration.benchmarks.cli --compare claude-3-5-sonnet gpt-4o

  # Output JSON report
  python -m quration.benchmarks.cli --output-dir ./results --json
        """,
    )

    # Task selection
    task_group = parser.add_argument_group("Task Selection")
    task_group.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmarks (default)",
    )
    task_group.add_argument(
        "--synthetic",
        action="store_true",
        help="Run only synthetic benchmarks",
    )
    task_group.add_argument(
        "--published",
        action="store_true",
        help="Run only published paper benchmarks",
    )
    task_group.add_argument(
        "--types",
        nargs="+",
        metavar="TYPE",
        help="Filter by task types (deg_analysis, batch_effect, pathway_enrichment, gene_function)",
    )
    task_group.add_argument(
        "--tags",
        nargs="+",
        metavar="TAG",
        help="Filter by tags (e.g., p53, immune, cancer)",
    )

    # Execution options
    exec_group = parser.add_argument_group("Execution Options")
    exec_group.add_argument(
        "--parallel",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel tasks (default: 1)",
    )
    exec_group.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECS",
        help="Timeout per task in seconds (default: 300)",
    )
    exec_group.add_argument(
        "--max-retries",
        type=int,
        default=2,
        metavar="N",
        help="Max retries per task (default: 2)",
    )

    # Model options
    model_group = parser.add_argument_group("Model Options")
    model_group.add_argument(
        "--model",
        type=str,
        metavar="MODEL",
        help="Model to use (default: from config)",
    )
    model_group.add_argument(
        "--compare",
        nargs="+",
        metavar="MODEL",
        help="Compare multiple models",
    )

    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--output-dir",
        type=str,
        default="benchmarks/results",
        metavar="DIR",
        help="Output directory for results (default: benchmarks/results)",
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    output_group.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to disk",
    )
    output_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    # LLM Judge options
    judge_group = parser.add_argument_group("LLM Judge Evaluation")
    judge_group.add_argument(
        "--judge",
        type=str,
        metavar="BENCHMARK_FILE",
        help="Re-evaluate a benchmark results file using LLM-as-judge (no re-running tasks)",
    )
    judge_group.add_argument(
        "--judge-model",
        type=str,
        default="claude-sonnet-4-5-20250929",
        metavar="MODEL",
        help="Model to use as judge (default: claude-sonnet-4-5-20250929)",
    )

    # CI options
    ci_group = parser.add_argument_group("CI Options")
    ci_group.add_argument(
        "--ci",
        action="store_true",
        help="Run in CI mode (strict thresholds, fail on issues)",
    )
    ci_group.add_argument(
        "--min-score",
        type=float,
        default=0.6,
        metavar="SCORE",
        help="Minimum overall score to pass (default: 0.6)",
    )
    ci_group.add_argument(
        "--max-hallucination",
        type=float,
        default=0.2,
        metavar="RATE",
        help="Maximum hallucination rate (default: 0.2)",
    )

    return parser


def print_summary(report, json_output: bool = False) -> None:
    """Print benchmark summary.

    Args:
        report: HarnessReport
        json_output: Output as JSON
    """
    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
        return

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    print(f"\nRun ID: {report.run_id}")
    print(f"Model: {report.model_used}")
    print(f"Started: {report.started_at.isoformat()}")
    print(f"Duration: {(report.completed_at - report.started_at).total_seconds():.1f}s")

    print(f"\n{'Tasks:':<20} {report.total_tasks}")
    print(f"{'Successful:':<20} {report.successful_tasks}")
    print(f"{'Failed:':<20} {report.failed_tasks}")
    print(f"{'Success Rate:':<20} {report.success_rate:.1%}")

    if report.aggregate_metrics:
        metrics = report.aggregate_metrics
        print("\n" + "-" * 40)
        print("AGGREGATE METRICS")
        print("-" * 40)

        def show(label: str, metric, raw: bool = False) -> None:
            """Print a metric, or say plainly that it was not measured.

            "not measured" has to be visible in the output. Printing nothing at
            all reads as "nothing to report", which is how a metric that never ran
            passed for a metric that came back clean.
            """
            if metric is None:
                print(f"{label:<25} not computed")
                return
            if not metric.measured:
                note = metric.details.get("note", "")
                print(f"{label:<25} not measured{f' — {note}' if note else ''}")
                return
            print(f"{label:<25} {(metric.value if raw else metric.normalized):.3f}")

        show("Accuracy:", metrics.accuracy)
        show("Completeness:", metrics.completeness)
        show("Claim Precision:", metrics.claim_precision)
        show("Claim Recall:", metrics.claim_recall)
        show("Hallucination Rate:", metrics.hallucination_rate, raw=True)
        show("Tool Utilization:", metrics.tool_utilization)

        # The score renormalises over whatever was measured, so it is not
        # comparable across runs with different coverage. State the coverage next
        # to it rather than letting the number stand alone.
        coverage = metrics.weight_coverage
        print(f"\n{'OVERALL SCORE:':<25} {metrics.overall_score:.3f}")
        print(
            f"{'  from weight coverage:':<25} {coverage:.0%}"
            + ("" if coverage >= 0.999 else "  (partial — not comparable across runs)")
        )

        # State the provenance of the number next to the number. The bundled suite is
        # 25 synthetic tasks and 6 grounded in real papers, and the default run mixes
        # them — so an unqualified score is mostly self-consistency against invented
        # ground truth, in exactly the form most likely to be pasted into a README.
        synthetic = report.synthetic_task_count
        if synthetic:
            print(
                f"{'  task ground truth:':<25} {synthetic} of {len(report.results)} "
                "tasks are SYNTHETIC"
            )
            print(
                "\n  NOT A PUBLISHABLE BENCHMARK NUMBER — this score is computed partly\n"
                "  over invented ground truth. Re-run with --published to score only the\n"
                "  tasks taken from real studies, and report that n alongside the number."
            )
        else:
            print(f"{'  task ground truth:':<25} all from published studies")

    if report.errors:
        print("\n" + "-" * 40)
        print("ERRORS")
        print("-" * 40)
        for error in report.errors:
            print(f"  - {error}")

    print("\n" + "=" * 60)


def check_ci_thresholds(
    report,
    min_score: float,
    max_hallucination: float,
) -> tuple[bool, list[str]]:
    """Check if results meet CI thresholds.

    Args:
        report: HarnessReport
        min_score: Minimum overall score
        max_hallucination: Maximum hallucination rate

    Returns:
        Tuple of (passed, failure_reasons)
    """
    failures = []

    if report.aggregate_metrics:
        if report.aggregate_metrics.overall_score < min_score:
            failures.append(
                f"Overall score {report.aggregate_metrics.overall_score:.3f} "
                f"< minimum {min_score}"
            )

        # A threshold you cannot evaluate must not silently pass. This used to read
        # `if report.aggregate_metrics.hallucination_rate:` — and the harness never
        # populates that field, so the value was always None, the branch was always
        # falsy, and --max-hallucination could never fail a run no matter what it
        # was set to. A gate that cannot fire is worse than no gate: it reports
        # assurance it never checked.
        hallucination = report.aggregate_metrics.hallucination_rate
        if hallucination is None:
            failures.append(
                "--max-hallucination was requested but hallucination_rate was not "
                "computed for this run, so the threshold could not be enforced"
            )
        elif not hallucination.measured:
            failures.append(
                "--max-hallucination was requested but hallucination_rate was not "
                f"measured: {hallucination.details.get('note', 'no detail given')}"
            )
        elif hallucination.value > max_hallucination:
            failures.append(
                f"Hallucination rate {hallucination.value:.3f} > maximum {max_hallucination}"
            )

    if report.success_rate < 0.8:
        failures.append(f"Success rate {report.success_rate:.1%} < 80%")

    return len(failures) == 0, failures


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = get_parser()
    args = parser.parse_args()

    setup_logging(args.verbose)

    # LLM Judge mode — re-evaluate existing results
    if args.judge:
        from quration.benchmarks.llm_judge import LLMJudge

        judge = LLMJudge(model=args.judge_model)
        report = await judge.evaluate_benchmark_file(args.judge)
        print(f"\nNormalized score: {report.normalized_score:.1%}")
        return 0

    # Configure harness
    config = HarnessConfig(
        parallel_tasks=args.parallel,
        max_retries=args.max_retries,
        timeout_seconds=args.timeout,
        output_dir=args.output_dir,
        save_detailed_results=not args.no_save,
        task_types=args.types,
        tags=args.tags,
    )

    # Create harness
    if args.model:
        from quration.interpretation.service import create_interpretation_service

        service = create_interpretation_service(model=args.model)
        harness = EvaluationHarness(config=config, service=service)
    else:
        harness = EvaluationHarness(config=config)

    # Register tasks based on selection
    if args.published and not args.synthetic:
        # Only published
        harness.register_tasks(get_all_published_tasks())
        logger.info("Registered published paper tasks")
    elif args.synthetic and not args.published:
        # Only synthetic
        harness.register_tasks(get_all_deg_tasks())
        harness.register_tasks(get_all_batch_tasks())
        harness.register_tasks(get_all_pathway_tasks())
        harness.register_tasks(get_all_gene_function_tasks())
        logger.info("Registered synthetic tasks")
    else:
        # All tasks
        harness.register_tasks(get_all_deg_tasks())
        harness.register_tasks(get_all_batch_tasks())
        harness.register_tasks(get_all_pathway_tasks())
        harness.register_tasks(get_all_gene_function_tasks())
        harness.register_tasks(get_all_published_tasks())
        logger.info("Registered all benchmark tasks")

    # Run benchmarks
    if args.compare:
        # Model comparison mode
        logger.info(f"Comparing models: {args.compare}")
        reports = await harness.compare_models(args.compare)

        print("\n" + "=" * 60)
        print("MODEL COMPARISON RESULTS")
        print("=" * 60)

        for model, report in reports.items():
            print(f"\n--- {model} ---")
            print_summary(report, args.json)

        # In CI mode, check all models
        if args.ci:
            all_passed = True
            for model, report in reports.items():
                passed, failures = check_ci_thresholds(
                    report, args.min_score, args.max_hallucination
                )
                if not passed:
                    all_passed = False
                    print(f"\n[FAIL] {model}:")
                    for f in failures:
                        print(f"  - {f}")
            return 0 if all_passed else 1

        return 0

    else:
        # Single model mode
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report = await harness.run(run_id=run_id)

        print_summary(report, args.json)

        # CI mode checks
        if args.ci:
            passed, failures = check_ci_thresholds(
                report, args.min_score, args.max_hallucination
            )

            if not passed:
                print("\n[CI FAILURE] Benchmark thresholds not met:")
                for f in failures:
                    print(f"  - {f}")
                return 1

            print("\n[CI PASSED] All thresholds met")

        return 0


def run():
    """Entry point for console script."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()
