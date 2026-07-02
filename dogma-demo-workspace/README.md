# Dogma Demo Workspace

Open this folder in a VS Code/Cursor extension development host with the Dogma extension loaded, then run:

```text
Dogma: Scan Workspace
```

Expected behavior:

- The Dogma Inspector sidebar lists domain findings.
- The Problems panel shows diagnostics with source `Dogma`.
- `Dogma: Open Assistant` shows parsed workspace context.
- The assistant can copy an AI-ready context prompt and write a synthetic test plan.
- `Dogma: Generate Context Report` writes `.dogma/context-report.md`.
- `Dogma: Preview Active Bio File` renders sample sheets, BED, VCF, and metadata JSON as tables.
- `Dogma: Generate Safe Run Plan` writes `.dogma/run-plan.md` with manual Nextflow stub-run guidance.
- The context report includes the detected Nextflow process/call graph.
- `pipeline.nf` gets a workflow warning because sample sheet rows are not validated before tuple creation.
- `sample_sheet.csv` gets duplicate and missing FASTQ findings.
- `intervals.bed` gets BED coordinate and chromosome naming findings.
- `variants.vcf` gets VCF reference/filter/depth findings.
- `metadata.json` gets provenance/privacy findings.

All records are synthetic.
