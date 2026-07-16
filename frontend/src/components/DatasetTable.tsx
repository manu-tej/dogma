import { useState } from 'react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Wrench, FileText, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import React from 'react';

interface Dataset {
  studyId: string;
  organism: string;
  tissue: string;
  sampleCount: number;
  platform: string;
  survivalData: boolean;
}

interface DatasetTableProps {
  datasets: Dataset[];
}

const bioinformaticsTools = {
  'Quality Control': [
    { name: 'FastQC', description: 'Quality control checks on raw sequence data', url: 'https://www.bioinformatics.babraham.ac.uk/projects/fastqc/' },
    { name: 'MultiQC', description: 'Aggregate results from bioinformatics analyses', url: 'https://multiqc.info/' },
    { name: 'Trimmomatic', description: 'Flexible read trimming tool for Illumina NGS data', url: 'http://www.usadellab.org/cms/?page=trimmomatic' },
  ],
  'Alignment': [
    { name: 'STAR', description: 'Ultrafast universal RNA-seq aligner', url: 'https://github.com/alexdobin/STAR' },
    { name: 'HISAT2', description: 'Graph-based alignment of next generation sequencing reads', url: 'http://daehwankimlab.github.io/hisat2/' },
    { name: 'Bowtie2', description: 'Fast and memory-efficient alignment tool', url: 'http://bowtie-bio.sourceforge.net/bowtie2/' },
  ],
  'Quantification': [
    { name: 'featureCounts', description: 'Efficient read counting for RNA-seq', url: 'http://subread.sourceforge.net/' },
    { name: 'Salmon', description: 'Fast transcript-level quantification', url: 'https://salmon.readthedocs.io/' },
    { name: 'RSEM', description: 'Accurate transcript quantification', url: 'https://deweylab.github.io/RSEM/' },
  ],
  'Differential Expression': [
    { name: 'DESeq2', description: 'Differential gene expression analysis (R/Bioconductor)', url: 'https://bioconductor.org/packages/DESeq2/' },
    { name: 'edgeR', description: 'Empirical analysis of DGE in R', url: 'https://bioconductor.org/packages/edgeR/' },
    { name: 'limma', description: 'Linear models for microarray and RNA-seq', url: 'https://bioconductor.org/packages/limma/' },
  ],
  'Functional Analysis': [
    { name: 'clusterProfiler', description: 'Statistical analysis and visualization of functional profiles', url: 'https://bioconductor.org/packages/clusterProfiler/' },
    { name: 'GSEA', description: 'Gene Set Enrichment Analysis', url: 'https://www.gsea-msigdb.org/' },
    { name: 'Enrichr', description: 'Comprehensive gene set enrichment analysis web server', url: 'https://maayanlab.cloud/Enrichr/' },
  ],
};

export function DatasetTable({ datasets }: DatasetTableProps) {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [toolsDialogOpen, setToolsDialogOpen] = useState(false);
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);

  const toggleRow = (idx: number) => {
    setExpandedRow(expandedRow === idx ? null : idx);
  };

  const openToolsDialog = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setToolsDialogOpen(true);
  };

  const openPlanDialog = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setPlanDialogOpen(true);
  };

  const generateAnalysisPlan = (dataset: Dataset) => {
    return {
      steps: [
        {
          phase: 'Phase 1: Data Acquisition & Quality Control',
          duration: '1-2 days',
          tasks: [
            'Download raw sequencing data from GEO/SRA',
            'Run FastQC to assess read quality',
            'Trim adapters and low-quality bases with Trimmomatic',
            'Generate MultiQC report for aggregate QC metrics',
          ],
        },
        {
          phase: 'Phase 2: Read Alignment',
          duration: '2-3 days',
          tasks: [
            `Align reads to ${dataset.organism} reference genome using STAR`,
            'Generate alignment statistics (mapping rate, duplicates)',
            'Visualize alignment in IGV for validation',
            'Sort and index BAM files',
          ],
        },
        {
          phase: 'Phase 3: Gene Quantification',
          duration: '1 day',
          tasks: [
            'Count reads per gene using featureCounts',
            'Calculate TPM/FPKM normalization',
            'Generate correlation heatmaps between samples',
            'Perform PCA for sample clustering',
          ],
        },
        {
          phase: 'Phase 4: Differential Expression Analysis',
          duration: '2-3 days',
          tasks: [
            'Run DESeq2 for differential expression',
            'Filter DEGs by log2FC > 1 and padj < 0.05',
            'Generate volcano plots and MA plots',
            'Create heatmaps of top DEGs',
          ],
        },
        {
          phase: 'Phase 5: Functional Enrichment',
          duration: '2 days',
          tasks: [
            'Perform GO enrichment analysis with clusterProfiler',
            'Run KEGG pathway analysis',
            'Execute GSEA for pathway-level insights',
            'Visualize enrichment results',
          ],
        },
        ...(dataset.survivalData
          ? [
              {
                phase: 'Phase 6: Survival Analysis',
                duration: '2-3 days',
                tasks: [
                  'Perform Kaplan-Meier survival analysis',
                  'Run Cox proportional hazards regression',
                  'Identify prognostic gene signatures',
                  'Generate survival curves and forest plots',
                ],
              },
            ]
          : []),
      ],
      estimatedTotalTime: dataset.survivalData ? '10-14 days' : '8-11 days',
      requiredResources: [
        'High-performance computing cluster (16+ cores, 64GB+ RAM)',
        'Reference genome and annotation files',
        'R/Bioconductor environment',
        'Python environment with bioinformatics packages',
      ],
    };
  };

  return (
    <>
      <div className="mt-4 border border-border rounded-lg overflow-hidden elev">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-1">
              <tr>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium w-8"></th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Study ID</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Organism</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Tissue/Cell Type</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Samples</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Platform</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Survival Data</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Tools</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">Analysis Plan</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((dataset: Dataset, idx: number) => (
                <React.Fragment key={idx}>
                  <tr
                    className="border-t border-border hover:bg-surface-1 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <button
                        onClick={() => toggleRow(idx)}
                        className="text-muted-foreground hover:text-foreground/90 transition-colors"
                      >
                        {expandedRow === idx ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </td>
                    <td className="py-3 px-4">
                      <code className="text-signal text-xs bg-surface-2 px-2 py-1 rounded font-mono">
                        {dataset.studyId}
                      </code>
                    </td>
                    <td className="py-3 px-4 text-foreground/90">{dataset.organism}</td>
                    <td className="py-3 px-4 text-foreground/90">{dataset.tissue}</td>
                    <td className="py-3 px-4 text-foreground/90 font-mono">{dataset.sampleCount}</td>
                    <td className="py-3 px-4 text-muted-foreground text-xs">{dataset.platform}</td>
                    <td className="py-3 px-4">
                      {dataset.survivalData ? (
                        <Badge className="bg-surface-2 text-positive border-border text-xs">
                          Available
                        </Badge>
                      ) : (
                        <Badge
                          variant="outline"
                          className="border-border text-muted-foreground/70 text-xs"
                        >
                          Not Available
                        </Badge>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openToolsDialog(dataset)}
                        className="text-signal hover:text-signal hover:bg-accent h-8"
                      >
                        <Wrench className="w-4 h-4 mr-1" />
                        View Tools
                      </Button>
                    </td>
                    <td className="py-3 px-4">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openPlanDialog(dataset)}
                        className="text-foreground/90 hover:text-foreground hover:bg-accent h-8"
                      >
                        <FileText className="w-4 h-4 mr-1" />
                        Generate Plan
                      </Button>
                    </td>
                  </tr>
                  {expandedRow === idx && (
                    <tr className="border-t border-border bg-surface-1">
                      <td colSpan={9} className="py-4 px-4">
                        <div className="space-y-3 text-sm">
                          <div>
                            <span className="text-muted-foreground">Study Description: </span>
                            <span className="text-foreground/90">
                              RNA-Seq analysis of {dataset.tissue} samples from {dataset.organism}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Recommended First Step: </span>
                            <span className="text-foreground/90">
                              Download and perform quality control with FastQC
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Estimated Analysis Time: </span>
                            <span className="text-foreground/90">
                              {dataset.survivalData ? '10-14 days' : '8-11 days'} (full pipeline)
                            </span>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bioinformatics Tools Dialog */}
      <Dialog open={toolsDialogOpen} onOpenChange={setToolsDialogOpen}>
        <DialogContent className="sm:max-w-[700px] bg-card border-border max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl flex items-center gap-2 text-foreground">
              <div className="p-2 rounded-lg bg-primary glow-signal">
                <Wrench className="w-5 h-5 text-primary-foreground" />
              </div>
              Bioinformatics Tools for {selectedDataset?.studyId}
            </DialogTitle>
            <DialogDescription className="text-base text-muted-foreground">
              Recommended tools for analyzing {selectedDataset?.organism} RNA-Seq data from{' '}
              {selectedDataset?.tissue}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            {Object.entries(bioinformaticsTools).map(([category, tools]) => (
              <div key={category} className="space-y-3">
                <h3 className="text-foreground flex items-center gap-2">
                  <Badge variant="secondary" className="bg-surface-2 text-foreground/90">
                    {category}
                  </Badge>
                </h3>
                <div className="space-y-2">
                  {tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="elev p-3 bg-surface-2 border border-border rounded-lg hover:-translate-y-0.5 hover:border-border-strong transition-[transform,box-shadow,border-color] duration-150 ease-out"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <code className="text-signal text-sm font-mono">{tool.name}</code>
                          </div>
                          <p className="text-muted-foreground text-sm mt-1">{tool.description}</p>
                        </div>
                        <a
                          href={tool.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-2 text-muted-foreground hover:text-signal transition-colors"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Analysis Plan Dialog */}
      <Dialog open={planDialogOpen} onOpenChange={setPlanDialogOpen}>
        <DialogContent className="sm:max-w-[700px] bg-card border-border max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl flex items-center gap-2 text-foreground">
              <div className="p-2 rounded-lg bg-surface-2 border border-border">
                <FileText className="w-5 h-5 text-signal" />
              </div>
              Analysis Plan for {selectedDataset?.studyId}
            </DialogTitle>
            <DialogDescription className="text-base text-muted-foreground">
              Comprehensive bioinformatics analysis workflow
            </DialogDescription>
          </DialogHeader>
          {selectedDataset && (
            <div className="space-y-6 py-4">
              {generateAnalysisPlan(selectedDataset).steps.map((step, idx) => (
                <div key={idx} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-foreground">{step.phase}</h3>
                    <Badge
                      variant="outline"
                      className="border-border text-muted-foreground text-xs font-mono"
                    >
                      {step.duration}
                    </Badge>
                  </div>
                  <ul className="space-y-2">
                    {step.tasks.map((task, taskIdx) => (
                      <li
                        key={taskIdx}
                        className="flex items-start gap-2 text-foreground/90 text-sm"
                      >
                        <span className="text-signal mt-1">•</span>
                        <span>{task}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}

              <div className="border-t border-border pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Estimated Total Time:</span>
                  <Badge className="bg-surface-2 text-signal border-signal/30 font-mono">
                    {generateAnalysisPlan(selectedDataset).estimatedTotalTime}
                  </Badge>
                </div>
                <div>
                  <h4 className="text-muted-foreground mb-2">Required Resources:</h4>
                  <ul className="space-y-1">
                    {generateAnalysisPlan(selectedDataset).requiredResources.map(
                      (resource, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-foreground/90 text-sm">
                          <span className="text-positive mt-1">✓</span>
                          <span>{resource}</span>
                        </li>
                      )
                    )}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}