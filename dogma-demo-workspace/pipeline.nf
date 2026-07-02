nextflow.enable.dsl = 2

params.samples = "sample_sheet.csv"
params.reference = "refs/GRCh38.fa"
params.outdir = "results"

process FASTQC {
  tag "$sample_id"

  input:
  tuple val(sample_id), path(reads)

  output:
  path "${sample_id}_fastqc.zip"

  script:
  """
  fastqc ${reads.join(" ")}
  """
}

process ALIGN_STAR {
  tag "$sample_id"

  input:
  tuple val(sample_id), path(reads)

  output:
  tuple val(sample_id), path("${sample_id}.bam")

  script:
  """
  STAR --genomeDir refs/star_GRCh38 --readFilesIn ${reads.join(" ")}
  """
}

workflow {
  Channel
    .fromPath(params.samples)
    .splitCsv(header: true)
    .map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }
    .set { sample_reads }

  FASTQC(sample_reads)
  ALIGN_STAR(sample_reads)
}
