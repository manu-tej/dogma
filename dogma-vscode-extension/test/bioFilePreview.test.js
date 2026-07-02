"use strict";

const assert = require("assert");
const { buildPreview, renderPreviewHtml } = require("../src/bioFilePreview");

const csvPreview = buildPreview("sample_sheet.csv", "sample_id,condition\nS1,control\nS2,treat");
assert.strictEqual(csvPreview.summary, "2 row(s), 2 column(s)");
assert(csvPreview.html.includes("<th>sample_id</th>"));

const bedPreview = buildPreview("targets.bed", "chr1\t10\t20\tregion");
assert.strictEqual(bedPreview.summary, "1 interval row(s). BED coordinates are 0-based half-open.");
assert(bedPreview.html.includes("<td>region</td>"));

const vcfPreview = buildPreview("variants.vcf", [
  "##fileformat=VCFv4.3",
  "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
  "chr1\t42\tv1\tA\tT\t99\tPASS\tDP=30;AF=0.5"
].join("\n"));
assert.strictEqual(vcfPreview.summary, "1 variant row(s). VCF POS is 1-based.");
assert(vcfPreview.html.includes("<td>0.5</td>"));

const annotationPreview = buildPreview("genes.gtf", 'chr1\tDogma\tgene\t100\t200\t.\t+\t.\tgene_id "G1";');
assert.strictEqual(annotationPreview.summary, "1 annotation feature row(s). GTF/GFF coordinates are 1-based closed.");
assert(annotationPreview.html.includes("<td>gene</td>"));
assert(annotationPreview.html.includes("gene_id"));

const fastqPreview = buildPreview("reads.fastq", "@r1\nACGT\n+\nIIII\n@r2\nGGCC\n+\nJJJJ\n");
assert.strictEqual(fastqPreview.summary, "2 read record(s), 8 observed base(s) in preview. FASTQ uses four lines per read.");
assert(fastqPreview.html.includes("<td>r1</td>"));
assert(fastqPreview.html.includes("<td>50</td>"));

const jsonPreview = buildPreview("metadata.json", JSON.stringify({ reference: { genome_build: "GRCh38" } }));
assert.strictEqual(jsonPreview.summary, "1 metadata field(s)");
assert(jsonPreview.html.includes("reference.genome_build"));

const html = renderPreviewHtml("sample_sheet.csv", "sample_id,condition\nS1,control");
assert(html.includes("<!doctype html>"));
assert(html.includes("Sample sheet preview"));

console.log("bio file preview tests passed");
