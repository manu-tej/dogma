"""Command-line interface for Quration."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from quration import MetadataCurator, get_config
from quration.storage.formats import OutputFormatter

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Quration: NGS Metadata Curation Framework.

    An LLM-powered tool for curating, standardizing, and enriching
    metadata from public NGS datasets.
    """
    pass


@main.command()
@click.argument("query")
@click.option(
    "--limit",
    "-l",
    default=5,
    type=int,
    help="Maximum number of datasets to curate",
    show_default=True,
)
@click.option(
    "--samples",
    "-s",
    default=10,
    type=int,
    help="Maximum samples per dataset",
    show_default=True,
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default="./data/output",
    help="Output directory",
    show_default=True,
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Configuration file path",
)
@click.option(
    "--smart",
    is_flag=True,
    help="Use smart model (Sonnet) instead of default fast model (Haiku)",
)
@click.option(
    "--show-cost",
    is_flag=True,
    help="Display cost estimate after completion",
)
@click.option(
    "--paired",
    is_flag=True,
    help="Find datasets with paired pre/post-treatment muscle biopsies (DMD pipeline)",
)
@click.option(
    "--survey",
    is_flag=True,
    help="With --paired: enumerate the whole human muscle landscape (relaxed gate), "
    "annotating each dataset's biopsy/pairing/treatment signals",
)
@click.option(
    "--disease",
    default="dmd",
    show_default=True,
    help="With --paired: disease to search. 'dmd' uses the curated profile; any other "
    "string runs a generic landscape search for that condition.",
)
def curate(
    query: str,
    limit: int,
    samples: int,
    output_dir: Path,
    config: Optional[Path],
    smart: bool,
    show_cost: bool,
    paired: bool,
    survey: bool,
    disease: str,
) -> None:
    """Curate metadata from GEO datasets matching QUERY.

    Example:
        quration curate "breast cancer RNA-seq 2023" --limit 5

    Use --paired to run the DMD paired pre/post-treatment biopsy discovery pipeline
    (ClinicalTrials.gov cross-reference + GEO search + LLM confirmation):
        quration curate "DMD" --paired --limit 40 --smart

    By default, uses Claude Haiku 4.5 (fast). Use --smart for Claude Sonnet 4.5.
    """
    if config:
        get_config(config_path=config, reload=True)

    if paired:
        _run_paired_search(
            limit=limit, output_dir=output_dir, smart=smart, survey=survey, disease=disease
        )
        return

    console.print(
        Panel.fit(
            f"[bold cyan]Quration[/bold cyan]\n"
            f"Query: [yellow]{query}[/yellow]\n"
            f"Max datasets: {limit} | Max samples per dataset: {samples}",
            title="NGS Metadata Curation",
        )
    )

    # Initialize curator
    try:
        # Invert the smart flag to match MetadataCurator's use_fast_model parameter
        use_fast_model = not smart
        curator = MetadataCurator(use_fast_model=use_fast_model)
        model_name = "Claude Sonnet 4.5 (Smart)" if smart else "Claude Haiku 4.5 (Fast)"
        console.print(f"[green]✓[/green] Using model: {model_name}")
    except ValueError as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        console.print(
            "\n[yellow]Tip:[/yellow] Set ANTHROPIC_API_KEY environment variable "
            "or configure in config.yaml"
        )
        return

    # Curate datasets
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Searching and curating datasets...", total=None)

        try:
            curated_datasets = curator.curate_from_query(query, limit=limit, samples_per_dataset=samples)
        except Exception as e:
            console.print(f"\n[red]✗ Error during curation:[/red] {e}")
            return

        progress.update(task, completed=True)

    if not curated_datasets:
        console.print("[yellow]No datasets found matching query.[/yellow]")
        return

    # Display results summary
    console.print(f"\n[green]✓[/green] Successfully curated {len(curated_datasets)} dataset(s)")

    # Create summary table
    table = Table(title="Curated Datasets Summary", show_header=True)
    table.add_column("Dataset ID", style="cyan")
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Samples", justify="right", style="magenta")
    table.add_column("Quality", justify="center", style="green")

    for dataset in curated_datasets:
        table.add_row(
            dataset.dataset_id,
            dataset.title[:50] + "..." if len(dataset.title) > 50 else dataset.title,
            str(dataset.sample_count),
            dataset.dataset_quality_metrics.quality_grade,
        )

    console.print(table)

    # Save outputs
    console.print(f"\n[cyan]Saving outputs to:[/cyan] {output_dir}")

    try:
        output_paths = OutputFormatter.save_all_formats(
            curated_datasets,
            output_dir,
            prefix="curated",
        )

        console.print("[green]✓[/green] Saved in formats:")
        for format_name, path in output_paths.items():
            console.print(f"  • {format_name.upper()}: {path}")

    except Exception as e:
        console.print(f"[red]✗ Error saving outputs:[/red] {e}")

    # Show cost estimate
    if show_cost:
        cost_info = curator.get_cost_estimate()

        console.print("\n[cyan]Cost Estimate:[/cyan]")
        console.print(f"  Model: {cost_info['model']}")
        console.print(f"  Total tokens: {cost_info['tokens']['input'] + cost_info['tokens']['output']:,}")
        console.print(
            f"  Cache hits: {cost_info['tokens']['cache_read']:,} "
            f"({cost_info['cost_usd']['cache_read']} USD saved)"
        )
        console.print(f"  [bold]Total cost: ${cost_info['cost_usd']['total']:.4f} USD[/bold]")


def _run_paired_search(
    limit: int, output_dir: Path, smart: bool, survey: bool = False, disease: str = "dmd"
) -> None:
    """Run the paired pre/post-treatment biopsy discovery pipeline for a disease."""
    from anthropic import Anthropic

    from quration.data_sources.disease_profiles import get_profile
    from quration.data_sources.paired_biopsy_search import PairedBiopsySearch, to_markdown

    profile = get_profile(disease)
    if not survey and not profile.has_treatments:
        console.print(
            f"[yellow]⚠[/yellow] No treatment vocabulary for '{disease}' — precision mode "
            "cannot enforce the treatment gate. Running in survey mode instead."
        )
        survey = True

    mode_line = (
        f"Mode: SURVEY — enumerate human {profile.name.upper()} muscle landscape"
        if survey
        else f"Scope: human, {profile.name.upper()} treatments, paired pre/post biopsies"
    )
    console.print(
        Panel.fit(
            "[bold cyan]Quration — paired-biopsy discovery[/bold cyan]\n"
            "ClinicalTrials.gov cross-ref + GEO search + LLM confirmation\n"
            f"{mode_line}",
            title="Paired Biopsy Pipeline",
        )
    )

    # Build an LLM client for the second pass (optional but recommended).
    config = get_config()
    llm_client = None
    model = None
    api_key = config.llm.anthropic.api_key
    if api_key:
        llm_client = Anthropic(api_key=api_key)
        model = (
            config.llm.anthropic.smart_model if smart else config.llm.anthropic.fast_model
        )
        console.print(
            f"[green]✓[/green] LLM second pass: "
            f"{'Sonnet (smart)' if smart else 'Haiku (fast)'}"
        )
    else:
        console.print(
            "[yellow]⚠[/yellow] No ANTHROPIC_API_KEY — running keyword filter only "
            "(no LLM confirmation)"
        )

    search = PairedBiopsySearch(llm_client=llm_client, model=model, profile=profile)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Searching trials, GEO, and confirming pairing...", total=None)
        try:
            candidates = search.run(
                max_geo=limit, use_llm=llm_client is not None, survey=survey
            )
        except Exception as e:
            console.print(f"\n[red]✗ Error during paired search:[/red] {e}")
            return

    if not candidates:
        console.print("[yellow]No paired pre/post-treatment biopsy datasets found.[/yellow]")
        return

    console.print(f"\n[green]✓[/green] Found {len(candidates)} candidate dataset(s)")

    table = Table(title="DMD Paired-Biopsy Candidates", show_header=True)
    table.add_column("GSE", style="cyan")
    table.add_column("Title", style="white", max_width=45)
    table.add_column("Samples", justify="right", style="magenta")
    table.add_column("Source", style="yellow")
    table.add_column("LLM", justify="center", style="green")
    for c in candidates:
        llm = c.llm_verdict or {}
        llm_cell = "✅" if llm.get("is_paired_pre_post") else ("❌" if c.llm_verdict else "—")
        table.add_row(
            c.gse_id,
            c.title[:45] + "..." if len(c.title) > 45 else c.title,
            str(c.n_samples or "?"),
            c.source,
            llm_cell,
        )
    console.print(table)

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "dmd_paired_biopsy_shortlist.md"
    md_path.write_text(to_markdown(candidates))
    console.print(f"\n[green]✓[/green] Shortlist written to: [cyan]{md_path}[/cyan]")


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default="config/config.yaml",
    help="Configuration file path",
    show_default=True,
)
def validate_config(config: Path) -> None:
    """Validate configuration file.

    Example:
        quration validate-config --config config/config.yaml
    """
    console.print(f"[cyan]Validating configuration:[/cyan] {config}")

    try:
        cfg = get_config(config_path=config, reload=True)
        console.print("[green]✓[/green] Configuration is valid!")

        # Show key settings
        console.print("\n[cyan]Key Settings:[/cyan]")
        console.print(f"  LLM Provider: {cfg.llm.provider}")
        console.print(f"  GEO Email: {cfg.data_sources.geo.email}")
        console.print(f"  Output Directory: {cfg.output.output_dir}")
        console.print(f"  Output Formats: {', '.join(cfg.output.formats)}")

    except FileNotFoundError:
        console.print(f"[red]✗ Configuration file not found:[/red] {config}")
        console.print(
            "\n[yellow]Tip:[/yellow] Copy config/config.example.yaml to config/config.yaml"
        )
    except Exception as e:
        console.print(f"[red]✗ Configuration error:[/red] {e}")


@main.command()
def init() -> None:
    """Initialize Quration configuration.

    Creates a config directory and example configuration file.
    """
    config_dir = Path("config")
    config_file = config_dir / "config.yaml"
    example_file = config_dir / "config.example.yaml"

    if config_file.exists():
        console.print(f"[yellow]Configuration already exists:[/yellow] {config_file}")
        if not click.confirm("Overwrite?"):
            return

    # Create config directory
    config_dir.mkdir(exist_ok=True)
    console.print(f"[green]✓[/green] Created directory: {config_dir}")

    # Copy example config (this assumes example exists in package)
    console.print(f"[green]✓[/green] Created configuration file: {config_file}")
    console.print(
        "\n[cyan]Next steps:[/cyan]\n"
        f"  1. Edit {config_file}\n"
        "  2. Add your ANTHROPIC_API_KEY\n"
        "  3. Add your NCBI email (required)\n"
        "  4. Run: quration curate \"your search query\""
    )


if __name__ == "__main__":
    main()
