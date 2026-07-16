"""
Results parser for nf-core pipeline outputs.

This module parses and summarizes results from nf-core pipelines,
extracting key metrics and outputs.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResultsParser:
    """Parse and summarize nf-core pipeline results."""

    def __init__(self, output_dir: Path):
        """
        Initialize the results parser.

        Args:
            output_dir: Pipeline output directory
        """
        self.output_dir = Path(output_dir)

    def parse_rnaseq_results(self) -> Dict[str, Any]:
        """
        Parse nf-core/rnaseq pipeline results.

        Returns:
            Dictionary with parsed results and metrics
        """
        results = {
            "pipeline": "nf-core/rnaseq",
            "output_dir": str(self.output_dir),
            "multiqc_report": None,
            "salmon_results": None,
            "star_results": None,
            "deseq2_results": None,
            "key_outputs": [],
            "summary_metrics": {},
        }

        # Find MultiQC report
        multiqc_html = self._find_file("multiqc_report.html")
        if multiqc_html:
            results["multiqc_report"] = str(multiqc_html)
            results["key_outputs"].append(("MultiQC Report", str(multiqc_html)))

        # Find Salmon quantification
        salmon_dir = self.output_dir / "salmon"
        if salmon_dir.exists():
            results["salmon_results"] = str(salmon_dir)
            results["key_outputs"].append(("Salmon Quantification", str(salmon_dir)))

            # Count samples
            sample_dirs = [d for d in salmon_dir.iterdir() if d.is_dir()]
            results["summary_metrics"]["samples_quantified"] = len(sample_dirs)

        # Find STAR alignment
        star_dir = self.output_dir / "star"
        if star_dir.exists():
            results["star_results"] = str(star_dir)
            results["key_outputs"].append(("STAR Alignment", str(star_dir)))

        # Find DESeq2 results
        deseq2_dir = self.output_dir / "deseq2"
        if deseq2_dir.exists():
            results["deseq2_results"] = str(deseq2_dir)
            results["key_outputs"].append(("DESeq2 Results", str(deseq2_dir)))

            # Count DE result files
            de_files = list(deseq2_dir.glob("*.results.csv"))
            results["summary_metrics"]["differential_expression_comparisons"] = len(de_files)

        # Find gene counts matrix
        counts_file = self._find_file("*gene.counts.tsv") or self._find_file("*merged_gene_counts.txt")
        if counts_file:
            results["key_outputs"].append(("Gene Counts Matrix", str(counts_file)))

        return results

    def parse_fetchngs_results(self) -> Dict[str, Any]:
        """
        Parse nf-core/fetchngs pipeline results.

        Returns:
            Dictionary with parsed results
        """
        results = {
            "pipeline": "nf-core/fetchngs",
            "output_dir": str(self.output_dir),
            "fastq_dir": None,
            "samplesheet": None,
            "key_outputs": [],
            "summary_metrics": {},
        }

        # Find FASTQ directory
        fastq_dir = self.output_dir / "fastq"
        if fastq_dir.exists():
            results["fastq_dir"] = str(fastq_dir)
            results["key_outputs"].append(("FASTQ Files", str(fastq_dir)))

            # Count FASTQ files
            fastq_files = list(fastq_dir.glob("*.fastq.gz")) + list(fastq_dir.glob("**/*.fastq.gz"))
            results["summary_metrics"]["fastq_files_downloaded"] = len(fastq_files)

        # Find samplesheet
        samplesheet = self._find_file("samplesheet.csv")
        if samplesheet:
            results["samplesheet"] = str(samplesheet)
            results["key_outputs"].append(("Samplesheet", str(samplesheet)))

        return results

    def parse_generic_results(self) -> Dict[str, Any]:
        """
        Parse generic nf-core pipeline results.

        Returns:
            Dictionary with common outputs
        """
        results = {
            "output_dir": str(self.output_dir),
            "multiqc_report": None,
            "pipeline_info": None,
            "key_outputs": [],
        }

        # Find MultiQC report (common to most pipelines)
        multiqc_html = self._find_file("multiqc_report.html")
        if multiqc_html:
            results["multiqc_report"] = str(multiqc_html)
            results["key_outputs"].append(("MultiQC Report", str(multiqc_html)))

        # Find pipeline info
        pipeline_info = self.output_dir / "pipeline_info"
        if pipeline_info.exists():
            results["pipeline_info"] = str(pipeline_info)

        return results

    def _find_file(self, pattern: str) -> Optional[Path]:
        """
        Find a file matching a pattern in the output directory.

        Args:
            pattern: Glob pattern to match

        Returns:
            Path to first matching file, or None
        """
        matches = list(self.output_dir.glob(f"**/{pattern}"))
        return matches[0] if matches else None

    def generate_summary_report(
        self, pipeline_type: str = "rnaseq"
    ) -> str:
        """
        Generate a text summary report of pipeline results.

        Args:
            pipeline_type: Type of pipeline

        Returns:
            Summary report as string
        """
        if pipeline_type == "rnaseq":
            results = self.parse_rnaseq_results()
        elif pipeline_type == "fetchngs":
            results = self.parse_fetchngs_results()
        else:
            results = self.parse_generic_results()

        report_lines = [
            f"Pipeline Results Summary",
            f"=" * 50,
            f"Output Directory: {results['output_dir']}",
            "",
            "Key Outputs:",
        ]

        for name, path in results.get("key_outputs", []):
            report_lines.append(f"  • {name}: {path}")

        if results.get("summary_metrics"):
            report_lines.append("")
            report_lines.append("Summary Metrics:")
            for metric, value in results["summary_metrics"].items():
                report_lines.append(f"  • {metric}: {value}")

        return "\n".join(report_lines)

    def save_results_summary(
        self, output_path: Path, pipeline_type: str = "rnaseq"
    ) -> None:
        """
        Save results summary to JSON file.

        Args:
            output_path: Path to save summary
            pipeline_type: Type of pipeline
        """
        if pipeline_type == "rnaseq":
            results = self.parse_rnaseq_results()
        elif pipeline_type == "fetchngs":
            results = self.parse_fetchngs_results()
        else:
            results = self.parse_generic_results()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Saved results summary to {output_path}")


class MultiQCParser:
    """Parse MultiQC report data."""

    def __init__(self, multiqc_data_path: Path):
        """
        Initialize MultiQC parser.

        Args:
            multiqc_data_path: Path to multiqc_data.json
        """
        self.data_path = multiqc_data_path

        if not self.data_path.exists():
            raise FileNotFoundError(f"MultiQC data not found: {multiqc_data_path}")

        with open(self.data_path, "r") as f:
            self.data = json.load(f)

    def get_general_stats(self) -> Dict[str, Any]:
        """Get general statistics from MultiQC report."""
        return self.data.get("report_general_stats_data", [])

    def get_fastqc_summary(self) -> Dict[str, Any]:
        """Get FastQC summary statistics."""
        return self.data.get("report_saved_raw_data", {}).get("multiqc_fastqc", {})

    def get_sample_names(self) -> List[str]:
        """Get list of sample names in the report."""
        general_stats = self.get_general_stats()
        if general_stats:
            return list(general_stats[0].keys())
        return []

    def extract_key_metrics(self) -> Dict[str, Any]:
        """Extract key quality metrics across all samples."""
        metrics = {
            "total_samples": len(self.get_sample_names()),
            "failed_samples": [],
            "warnings": [],
        }

        # Analyze FastQC data
        fastqc_data = self.get_fastqc_summary()
        if fastqc_data:
            for sample, data in fastqc_data.items():
                # Check for failures
                if data.get("basic_statistics") == "fail":
                    metrics["failed_samples"].append(sample)

        return metrics
