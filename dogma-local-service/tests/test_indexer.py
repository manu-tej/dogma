from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from biocursor_service.indexer import classify_file, scan_workspace


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class IndexerTests(unittest.TestCase):
    def test_scan_demo_workspace_finds_domain_context_and_risks(self) -> None:
        result = scan_workspace(DEMO_ROOT)
        codes = {issue["code"] for issue in result["issues"]}

        self.assertEqual(result["service"], "dogma-local-service")
        self.assertEqual(result["summary"]["risk_level"], "blocked")
        self.assertGreaterEqual(result["summary"]["errors"], 1)
        self.assertIn("sample_sheet.duplicate_sample_id", codes)
        self.assertIn("sample_sheet.missing_fastq_pair", codes)
        self.assertIn("bed.invalid_interval", codes)
        self.assertIn("bed.mixed_chromosome_names", codes)
        self.assertIn("vcf.missing_reference", codes)
        self.assertIn("vcf.non_pass_filters", codes)
        self.assertIn("metadata.missing_annotation", codes)
        self.assertIn("metadata.missing_sample_id_policy", codes)
        self.assertIn("nextflow.sample_sheet_validation", codes)

        context = result["context"]
        self.assertEqual(context["sample_file"], "sample_sheet.csv")
        self.assertIn("genes.gtf", [item["path"] for item in context["annotation_files"]])
        self.assertEqual(context["annotation_files"][0]["features"], 3)
        self.assertIn("genes.gtf", result["summary"]["annotation_files"])
        self.assertIn("reads/SYN_004_R1.fastq", [item["path"] for item in context["fastq_files"]])
        self.assertEqual(result["summary"]["fastq_reads"], 2)
        self.assertIn("pipeline.nf", context["workflow_files"])
        self.assertIn("ALIGN_STAR", context["workflow_processes"])
        self.assertIn("FASTQC", context["workflow_processes"])
        self.assertEqual(result["summary"]["samples"], 3)
        self.assertEqual(result["trust"]["status"], "untrusted")
        self.assertEqual(result["trust"]["human_data"], True)
        self.assertTrue(result["trust"]["blockers"])

    def test_scan_collects_reference_qc_and_large_file_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample_sheet.csv").write_text(
                "sample_id,fastq_1,fastq_2,condition,strandedness\n"
                "S1,reads/S1_R1.fastq.gz,reads/S1_R2.fastq.gz,treated,reverse\n",
                encoding="utf-8",
            )
            (root / "genome.fa.fai").write_text("chr1\t248956422\t6\t80\t81\nchr2\t242193529\t252427357\t80\t81\n", encoding="utf-8")
            (root / "multiqc_data").mkdir()
            (root / "multiqc_data" / "multiqc_general_stats.txt").write_text("Sample\tFastQC_mqc-generalstats-fastqc-percent_duplicates\nS1\t12.5\n", encoding="utf-8")
            (root / "genes.gff3").write_text("##gff-version 3\nchr1\tDogma\tgene\t100\t200\t.\t+\t.\tID=gene1;Name=Gene1\n", encoding="utf-8")
            (root / "reads").mkdir()
            with gzip.open(root / "reads" / "S1_R1.fastq.gz", "wt", encoding="utf-8") as handle:
                handle.write("@S1/1\nACGT\n+\nIIII\n")
            with gzip.open(root / "reads" / "S1_R2.fastq.gz", "wt", encoding="utf-8") as handle:
                handle.write("@S1/2\nTGCA\n+\nIIII\n")
            (root / "alignments.bam").write_bytes(b"")
            (root / "archive.cram").write_bytes(b"")

            result = scan_workspace(root)

        self.assertEqual(result["summary"]["risk_level"], "ready")
        self.assertEqual(result["context"]["reference"]["contigs"][0]["name"], "chr1")
        self.assertEqual(result["context"]["qc_reports"][0]["samples"], 1)
        self.assertEqual(result["context"]["qc_reports"][0]["metrics"], 1)
        self.assertEqual(result["context"]["annotation_files"][0]["path"], "genes.gff3")
        self.assertEqual(result["context"]["annotation_files"][0]["features"], 1)
        self.assertEqual(result["context"]["fastq_files"][0]["reads"], 1)
        self.assertEqual(len(result["context"]["data_inventory"]["fastq"]), 2)
        self.assertEqual(result["context"]["data_inventory"]["bam"], ["alignments.bam"])
        self.assertEqual(result["context"]["data_inventory"]["cram"], ["archive.cram"])

    def test_scan_reads_compressed_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with gzip.open(root / "variants.vcf.gz", "wt", encoding="utf-8") as handle:
                handle.write("##fileformat=VCFv4.3\n##reference=GRCh38\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchr1\t10\t.\tA\tG\t60\tPASS\t.\n")
            with gzip.open(root / "intervals.bed.gz", "wt", encoding="utf-8") as handle:
                handle.write("chr1\t0\t10\n")
            with gzip.open(root / "genes.gtf.gz", "wt", encoding="utf-8") as handle:
                handle.write("chr1\tDogma\tgene\t100\t200\t.\t+\t.\tgene_id \"gene1\";\n")
            with gzip.open(root / "reads.fastq.gz", "wt", encoding="utf-8") as handle:
                handle.write("@r1\nACGT\n+\nIIII\n")

            result = scan_workspace(root)

        paths = {item["path"]: item["type"] for item in result["files"]}
        self.assertEqual(paths["variants.vcf.gz"], "vcf")
        self.assertEqual(paths["intervals.bed.gz"], "bed")
        self.assertEqual(paths["genes.gtf.gz"], "annotation")
        self.assertEqual(paths["reads.fastq.gz"], "fastq")
        self.assertEqual(result["summary"]["fastq_reads"], 1)
        self.assertEqual(result["summary"]["risk_level"], "ready")

    def test_scan_reports_fastq_structure_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.fastq").write_text("not_a_header\nACGTX\n-\nIII\norphan\n", encoding="utf-8")

            result = scan_workspace(root)

        codes = {issue["code"] for issue in result["issues"]}
        self.assertEqual(result["summary"]["risk_level"], "blocked")
        self.assertIn("fastq.incomplete_record", codes)
        self.assertIn("fastq.invalid_header", codes)
        self.assertIn("fastq.invalid_bases", codes)
        self.assertIn("fastq.quality_length_mismatch", codes)

    def test_classifies_expected_file_types(self) -> None:
        self.assertEqual(classify_file(Path("sample_sheet.csv.gz")), "sample_sheet")
        self.assertEqual(classify_file(Path("cohort.vcf.gz")), "vcf")
        self.assertEqual(classify_file(Path("targets.bed.gz")), "bed")
        self.assertEqual(classify_file(Path("genes.gtf")), "annotation")
        self.assertEqual(classify_file(Path("annotation.gff3.gz")), "annotation")
        self.assertEqual(classify_file(Path("reads.fastq.gz")), "fastq")
        self.assertEqual(classify_file(Path("sample.bam")), "bam")
        self.assertEqual(classify_file(Path("sample.cram")), "cram")
        self.assertEqual(classify_file(Path("Snakefile")), "snakemake")
        self.assertEqual(classify_file(Path("rules/qc.smk")), "snakemake")

    def test_invalid_workspace_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            scan_workspace(DEMO_ROOT / "missing")


if __name__ == "__main__":
    unittest.main()
