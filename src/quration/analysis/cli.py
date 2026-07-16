"""
Command-line interface for the quration analysis module.

Provides commands for generating analysis plans, downloading data,
and executing nf-core pipelines.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .config_generator import ConfigGenerator
from .data_fetcher import DataFetcher
from .models import ComputeEnvironment, PipelineType
from .nextflow_executor import (
    NextflowExecutor,
    check_nextflow_available,
    install_nextflow_instructions,
)
from .pipeline_registry import PipelineRegistry
from .plan_generator import AnalysisPlanGenerator

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def main(log_level: str):
    """Quration Analysis - NGS analysis using nf-core pipelines."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@main.command()
@click.argument("curated_dataset_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for analysis plan JSON",
)
@click.option(
    "--model",
    default="claude-3-5-sonnet-20241022",
    help="LLM model to use for plan generation",
)
def plan(curated_dataset_path: str, output: Optional[str], model: str):
    """Generate an analysis plan from curated dataset metadata."""
    console.print(f"\n[bold blue]Generating analysis plan for:[/bold blue] {curated_dataset_path}")

    # Load curated dataset
    with open(curated_dataset_path, "r") as f:
        curated_dataset = json.load(f)

    # Generate plan
    try:
        plan_generator = AnalysisPlanGenerator(model=model)
        analysis_plan = plan_generator.generate_plan(curated_dataset)

        # Display plan
        console.print("\n[bold green]✓ Analysis Plan Generated[/bold green]\n")

        console.print(f"[bold]Dataset:[/bold] {analysis_plan.dataset_id}")
        console.print(f"[bold]Title:[/bold] {analysis_plan.dataset_title}")
        console.print(f"[bold]Organism:[/bold] {analysis_plan.organism}")
        console.print(f"[bold]Library Strategy:[/bold] {analysis_plan.library_strategy}")
        console.print(f"[bold]Sample Count:[/bold] {analysis_plan.sample_count}")
        console.print(f"[bold]Paired-end:[/bold] {analysis_plan.has_paired_end}")

        console.print(f"\n[bold]Primary Pipeline:[/bold] {analysis_plan.primary_pipeline.value}")
        console.print(
            f"[bold]Recommended Pipelines:[/bold] {', '.join(p.value for p in analysis_plan.recommended_pipelines)}"
        )

        console.print(f"\n[bold]Reference Genome:[/bold] {analysis_plan.suggested_genome.name}")

        if analysis_plan.comparison_groups:
            console.print(f"\n[bold]Comparison Groups:[/bold]")
            for cg in analysis_plan.comparison_groups:
                console.print(
                    f"  • {cg.name}: {cg.condition_a} ({len(cg.sample_ids_a)} samples) vs "
                    f"{cg.condition_b} ({len(cg.sample_ids_b)} samples)"
                )

        console.print(f"\n[bold]Rationale:[/bold]")
        console.print(f"  {analysis_plan.rationale}")

        console.print(f"\n[bold]Expected Outputs:[/bold]")
        for output_item in analysis_plan.expected_outputs:
            console.print(f"  • {output_item}")

        if analysis_plan.estimated_runtime:
            console.print(f"\n[bold]Estimated Runtime:[/bold] {analysis_plan.estimated_runtime}")

        # Save plan
        if output:
            output_path = Path(output)
        else:
            output_path = Path(curated_dataset_path).parent / f"{analysis_plan.dataset_id}_analysis_plan.json"

        plan_generator.save_plan(analysis_plan, output_path)
        console.print(f"\n[bold green]✓ Plan saved to:[/bold green] {output_path}")

    except Exception as e:
        console.print(f"[bold red]✗ Error generating plan:[/bold red] {e}", style="bold red")
        logger.exception("Failed to generate analysis plan")
        sys.exit(1)


@main.command()
@click.argument("dataset_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="./data/raw",
    help="Output directory for downloaded files",
)
@click.option(
    "--email",
    required=True,
    help="Email for NCBI API (required)",
)
@click.option(
    "--api-key",
    help="NCBI API key for higher rate limits (optional)",
)
@click.option(
    "--method",
    type=click.Choice(["ftp", "sratools", "aspera"]),
    default="ftp",
    help="Download method",
)
@click.option(
    "--for-pipeline",
    default="rnaseq",
    help="Format output for specific nf-core pipeline",
)
def fetch(
    dataset_id: str,
    output_dir: str,
    email: str,
    api_key: Optional[str],
    method: str,
    for_pipeline: str,
):
    """Download raw data from GEO/SRA using nf-core/fetchngs."""
    console.print(f"\n[bold blue]Fetching data for:[/bold blue] {dataset_id}")

    # Check Nextflow
    if not check_nextflow_available():
        console.print("[bold red]✗ Nextflow is not installed[/bold red]")
        console.print(install_nextflow_instructions())
        sys.exit(1)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        fetcher = DataFetcher(email=email, api_key=api_key)

        # Fetch data
        console.print(f"[bold]Using download method:[/bold] {method}")
        console.print(f"[bold]Output directory:[/bold] {output_path}")

        result = fetcher.fetch_from_geo(
            geo_id=dataset_id,
            output_dir=output_path,
            download_method=method,
            for_pipeline=for_pipeline,
            wait=True,
        )

        if result.status.value == "completed":
            console.print(f"\n[bold green]✓ Data download completed[/bold green]")
            console.print(f"[bold]Output:[/bold] {result.output_dir}")

            # Find FASTQ directory
            fastq_dir = fetcher.get_fastq_directory(Path(result.output_dir))
            if fastq_dir:
                console.print(f"[bold]FASTQ files:[/bold] {fastq_dir}")
        else:
            console.print(f"[bold red]✗ Download failed[/bold red]")
            if result.error_message:
                console.print(f"[bold]Error:[/bold] {result.error_message}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        logger.exception("Failed to fetch data")
        sys.exit(1)


@main.command()
@click.argument("pipeline_type", type=click.Choice([p.value for p in PipelineType]))
@click.argument("dataset_id")
@click.option(
    "--input",
    "-i",
    required=True,
    type=click.Path(exists=True),
    help="Input samplesheet or FASTQ directory",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="./results",
    help="Output directory",
)
@click.option(
    "--genome",
    help="Reference genome (e.g., GRCh38)",
)
@click.option(
    "--profile",
    multiple=True,
    default=["docker"],
    help="Nextflow profiles (can specify multiple)",
)
@click.option(
    "--resume/--no-resume",
    default=False,
    help="Resume previous run",
)
def run(
    pipeline_type: str,
    dataset_id: str,
    input: str,
    output_dir: str,
    genome: Optional[str],
    profile: tuple,
    resume: bool,
):
    """Run a specific nf-core pipeline."""
    console.print(f"\n[bold blue]Running {pipeline_type} pipeline[/bold blue]")

    # Check Nextflow
    if not check_nextflow_available():
        console.print("[bold red]✗ Nextflow is not installed[/bold red]")
        console.print(install_nextflow_instructions())
        sys.exit(1)

    try:
        # This is a simplified version - in practice, you'd build proper config
        # from the analysis plan
        console.print("[bold yellow]Note:[/bold yellow] Use 'workflow' command for automated analysis")
        console.print("This command requires manual configuration")

        # TODO: Implement manual pipeline execution
        console.print("[bold red]Manual execution not yet implemented[/bold red]")
        console.print("Please use the 'workflow' command instead")

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        logger.exception("Failed to run pipeline")
        sys.exit(1)


@main.command()
def list_pipelines():
    """List all available nf-core pipelines."""
    console.print("\n[bold blue]Available nf-core Pipelines[/bold blue]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Pipeline", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Description")
    table.add_column("Library Strategies")

    for pipeline_meta in PipelineRegistry.list_all_pipelines():
        strategies = ", ".join(pipeline_meta.supported_library_strategies)
        if len(strategies) > 50:
            strategies = strategies[:47] + "..."

        table.add_row(
            pipeline_meta.name,
            pipeline_meta.latest_version,
            pipeline_meta.description[:60] + "..." if len(pipeline_meta.description) > 60 else pipeline_meta.description,
            strategies,
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(PipelineRegistry.PIPELINES)} pipelines")


@main.command()
def check_setup():
    """Check if Nextflow and dependencies are installed."""
    console.print("\n[bold blue]Checking Analysis Module Setup[/bold blue]\n")

    # Check Nextflow
    if check_nextflow_available():
        console.print("[bold green]✓ Nextflow is installed[/bold green]")
        executor = NextflowExecutor()
        version = executor._get_nextflow_version()
        if version:
            console.print(f"  {version}")
    else:
        console.print("[bold red]✗ Nextflow is not installed[/bold red]")
        console.print("\n" + install_nextflow_instructions())

    # Check Docker
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            console.print("[bold green]✓ Docker is installed[/bold green]")
            console.print(f"  {result.stdout.decode().strip()}")
        else:
            console.print("[bold yellow]⚠ Docker not found[/bold yellow]")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print("[bold yellow]⚠ Docker not found[/bold yellow]")

    console.print("\n[bold]Environment:[/bold]")
    console.print(f"  Python: {sys.version.split()[0]}")

    console.print("\n[bold green]✓ Setup check complete[/bold green]")


if __name__ == "__main__":
    main()
