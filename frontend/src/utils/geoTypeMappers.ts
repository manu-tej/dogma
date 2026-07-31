/**
 * Type transformation utilities for converting GEO dataset types to frontend Dataset types
 */

import type { GeoDatasetCandidate } from '../lib/geo-client/types';

/**
 * Frontend Dataset interface used by DatasetTable
 */
export interface Dataset {
  studyId: string;
  organism: string;
  tissue: string;
  sampleCount: number;
  platform: string;
  /**
   * The backend field is `maybe_has_survival_data` — a heuristic over the study
   * metadata, not a confirmed fact. The name keeps the "maybe", because dropping
   * it is how a guess became a green "Available" badge and a definite sentence in
   * the summary text.
   */
  maybeHasSurvivalData: boolean;
  /**
   * The study's own abstract, straight from GEO. Undefined when GEO did not
   * supply one — in which case say so, rather than composing a sentence. This
   * field was fetched and then thrown away, while the UI rendered a synthesized
   * "Study Description" in its place.
   */
  summary?: string;
}

/**
 * Common organism mappings for normalization
 */
const ORGANISM_PATTERNS: Record<string, RegExp> = {
  'Human': /\b(human|homo sapiens)\b/i,
  'Mouse': /\b(mouse|mus musculus)\b/i,
  'Rat': /\b(rat|rattus norvegicus)\b/i,
  'Zebrafish': /\b(zebrafish|danio rerio)\b/i,
  'Drosophila': /\b(drosophila|fruit fly|d\. melanogaster)\b/i,
  'C. elegans': /\b(c\. elegans|caenorhabditis elegans|worm)\b/i,
  'Yeast': /\b(yeast|saccharomyces cerevisiae|s\. cerevisiae)\b/i,
  'Arabidopsis': /\b(arabidopsis|a\. thaliana)\b/i,
};

/**
 * Common tissue/cell type keywords for extraction
 */
const TISSUE_KEYWORDS = [
  'blood', 'plasma', 'serum', 'pbmc', 'peripheral blood',
  'brain', 'liver', 'lung', 'heart', 'kidney', 'muscle',
  'skin', 'bone', 'adipose', 'fat', 'tissue',
  'tumor', 'cancer', 'carcinoma', 'melanoma', 'leukemia',
  'cell line', 'cells', 'fibroblast', 'epithelial', 'endothelial',
  'lymphocyte', 't cell', 'b cell', 'macrophage', 'monocyte',
  'stem cell', 'neural', 'neuronal', 'astrocyte', 'microglia',
  'hepatocyte', 'pancreatic', 'intestinal', 'colon', 'gastric',
  'breast', 'ovarian', 'prostate', 'testicular', 'uterine',
  'lymph node', 'spleen', 'thymus', 'bone marrow',
];

/**
 * Extract organism from text by matching common organism patterns
 *
 * @param text - Text to search for organism mentions
 * @returns Normalized organism name or 'Unknown' if not found
 *
 * @example
 * extractOrganism("RNA-seq of human breast cancer cells") // "Human"
 * extractOrganism("Mus musculus liver samples") // "Mouse"
 */
export function extractOrganism(text: string): string {
  if (!text) return 'Unknown';

  // Check against known organism patterns
  for (const [organism, pattern] of Object.entries(ORGANISM_PATTERNS)) {
    if (pattern.test(text)) {
      return organism;
    }
  }

  return 'Unknown';
}

/**
 * Extract tissue/cell type from text using keyword matching
 *
 * @param text - Text to search for tissue/cell type mentions
 * @returns Capitalized tissue/cell type or 'Unknown' if not found
 *
 * @example
 * extractTissue("RNA-seq of human breast cancer cells") // "Breast"
 * extractTissue("Analysis of peripheral blood mononuclear cells") // "PBMC"
 */
export function extractTissue(text: string): string {
  if (!text) return 'Unknown';

  const lowerText = text.toLowerCase();

  // Find the first matching tissue keyword
  for (const keyword of TISSUE_KEYWORDS) {
    if (lowerText.includes(keyword)) {
      // Capitalize the first letter of each word
      return keyword
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    }
  }

  return 'Unknown';
}

/**
 * Extract organism from GeoDatasetCandidate metadata
 * Searches in rawMetadata.organism, summary, and title
 *
 * @param geo - GeoDatasetCandidate object
 * @returns Normalized organism name
 */
function getOrganismFromGeoData(geo: GeoDatasetCandidate): string {
  // First check top-level organism field (from backend extraction)
  if (geo.organism) {
    const organism = extractOrganism(geo.organism);
    if (organism !== 'Unknown') return organism;
  }

  // Fallback to rawMetadata.organism if available
  if (geo.rawMetadata?.organism) {
    const organism = extractOrganism(geo.rawMetadata.organism);
    if (organism !== 'Unknown') return organism;
  }

  // Then check summary
  if (geo.summary) {
    const organism = extractOrganism(geo.summary);
    if (organism !== 'Unknown') return organism;
  }

  // Finally check title
  if (geo.title) {
    const organism = extractOrganism(geo.title);
    if (organism !== 'Unknown') return organism;
  }

  return 'Unknown';
}

/**
 * Extract tissue/cell type from GeoDatasetCandidate metadata
 * Searches in experimentalDesign.notes, summary, and title
 *
 * @param geo - GeoDatasetCandidate object
 * @returns Tissue/cell type name
 */
function getTissueFromGeoData(geo: GeoDatasetCandidate): string {
  // First check experimental design notes
  if (geo.experimentalDesign?.notes) {
    const tissue = extractTissue(geo.experimentalDesign.notes);
    if (tissue !== 'Unknown') return tissue;
  }

  // Then check summary
  if (geo.summary) {
    const tissue = extractTissue(geo.summary);
    if (tissue !== 'Unknown') return tissue;
  }

  // Finally check title
  if (geo.title) {
    const tissue = extractTissue(geo.title);
    if (tissue !== 'Unknown') return tissue;
  }

  return 'Unknown';
}

/**
 * Convert platforms array to a single platform string
 *
 * @param platforms - Array of platform names
 * @returns Comma-separated platform string or 'Unknown' if empty
 */
function formatPlatforms(platforms: string[] | null | undefined): string {
  if (!platforms || platforms.length === 0) {
    return 'Unknown';
  }

  // If only one platform, return it
  if (platforms.length === 1) {
    return platforms[0];
  }

  // If multiple platforms, join with comma and space
  return platforms.join(', ');
}

/**
 * Transform a GeoDatasetCandidate into a Dataset for the frontend table
 *
 * @param geo - GeoDatasetCandidate from the GEO search API
 * @returns Dataset object compatible with DatasetTable component
 *
 * @example
 * ```typescript
 * const geoData: GeoDatasetCandidate = {
 *   gseId: "GSE12345",
 *   title: "RNA-seq of human breast cancer cells treated with checkpoint inhibitors",
 *   summary: "We performed RNA-seq on human MCF-7 breast cancer cells...",
 *   experimentalDesign: {
 *     conditions: [
 *       { name: "control", n: 3 },
 *       { name: "treated", n: 3 }
 *     ],
 *     designType: "case-control",
 *     tech: "Illumina HiSeq 2500",
 *     notes: "Breast cancer cells from human samples",
 *     isPartial: false
 *   },
 *   nSamples: 6,
 *   platforms: ["GPL16791"],
 *   primaryPmid: "12345678",
 *   maybeHasSurvivalData: true,
 *   matchReasons: ["Found 'checkpoint inhibitor' in title"],
 *   rawMetadata: { organism: "Homo sapiens" },
 *   matchedQueries: ["checkpoint inhibitor breast cancer"]
 * };
 *
 * const dataset = transformGeoDataset(geoData);
 * // Result:
 * // {
 * //   studyId: "GSE12345",
 * //   organism: "Human",
 * //   tissue: "Breast",
 * //   sampleCount: 6,
 * //   platform: "GPL16791",
 * //   maybeHasSurvivalData: true
 * // }
 * ```
 */
export function transformGeoDataset(geo: GeoDatasetCandidate): Dataset {
  return {
    studyId: geo.gseId,
    organism: getOrganismFromGeoData(geo),
    tissue: getTissueFromGeoData(geo),
    sampleCount: geo.nSamples ?? 0,
    platform: formatPlatforms(geo.platforms),
    maybeHasSurvivalData: geo.maybeHasSurvivalData ?? false,
    // Carried through rather than mined and dropped. getOrganismFromGeoData and
    // getTissueFromGeoData already read this field to extract terms; the abstract
    // itself was then discarded, and the UI displayed a template sentence under
    // the heading "Study Description".
    summary: geo.summary?.trim() || undefined,
  };
}

/**
 * Transform an array of GeoDatasetCandidates into Dataset array
 *
 * @param geoDatasets - Array of GeoDatasetCandidate objects
 * @returns Array of Dataset objects
 *
 * @example
 * ```typescript
 * const geoResults = await searchGeoDatasets(query);
 * const datasets = transformGeoDatasets(geoResults);
 * <DatasetTable datasets={datasets} />
 * ```
 */
export function transformGeoDatasets(geoDatasets: GeoDatasetCandidate[]): Dataset[] {
  return geoDatasets.map(transformGeoDataset);
}

/**
 * Interface matching the existing analysis data structure in bioResponses.ts
 */
export interface AnalysisData {
  datasets: number;
  totalSamples: number | string;
  organisms: string;
  platform: string;
  datasetDetails: Dataset[];
}

/**
 * Maps an array of GeoDatasetCandidates to the existing AnalysisData format
 * Used by ChatInterface to display dataset search results
 *
 * @param candidates - Array of GeoDatasetCandidate from the API
 * @returns AnalysisData compatible with existing UI components
 *
 * @example
 * ```typescript
 * const geoResults = await client.searchGeo(spec);
 * const analysisData = mapGeoDatasetToAnalysis(geoResults);
 * // Use in BioResponse: { content: "...", analysis: { type: "Dataset Search Results", data: analysisData } }
 * ```
 */
export function mapGeoDatasetToAnalysis(candidates: GeoDatasetCandidate[]): AnalysisData {
  const datasetDetails = transformGeoDatasets(candidates);

  // Calculate total samples
  const totalSamples = datasetDetails.reduce((sum, d) => sum + (d.sampleCount || 0), 0);

  // Extract unique organisms
  const uniqueOrganisms = [...new Set(datasetDetails.map(d => d.organism).filter(o => o !== 'Unknown'))];
  const organisms = uniqueOrganisms.length === 1
                    ? uniqueOrganisms[0]
                    : uniqueOrganisms.length > 1
                    ? 'Multiple'
                    : 'Unknown';

  // Extract unique platforms
  const uniquePlatforms = [...new Set(datasetDetails.map(d => d.platform).filter(p => p !== 'Unknown'))];
  const platform = uniquePlatforms.length === 1
                   ? uniquePlatforms[0]
                   : uniquePlatforms.length > 1
                   ? 'Multiple'
                   : 'Unknown';

  return {
    datasets: candidates.length,
    totalSamples,
    organisms,
    platform,
    datasetDetails
  };
}

/**
 * Generates a natural language summary from GeoDatasetCandidates
 * Creates markdown-formatted content compatible with existing BioResponse structure
 *
 * @param candidates - Array of GeoDatasetCandidate from the API
 * @param query - Original user query
 * @returns Formatted markdown string with dataset summary
 *
 * @example
 * ```typescript
 * const geoResults = await client.searchGeo(spec);
 * const content = generateGeoResponseContent(geoResults, "breast cancer datasets");
 * // Returns: "I found **24** datasets in the GEO database matching your query..."
 * ```
 */
export function generateGeoResponseContent(
  candidates: GeoDatasetCandidate[],
  query: string
): string {
  if (candidates.length === 0) {
    return `I searched the GEO database but didn't find any datasets matching your query: "${query}".

**Suggestions:**
- Try broadening your search terms
- Check for alternative terminology
- Reduce minimum sample requirements
- Remove strict filters like survival data requirements`;
  }

  const analysisData = mapGeoDatasetToAnalysis(candidates);
  const totalSamples = typeof analysisData.totalSamples === 'number'
                       ? analysisData.totalSamples.toLocaleString()
                       : analysisData.totalSamples;

  // Count datasets that MAY have survival data.
  //
  // Numerator and denominator must describe the same population. The count ran
  // over every candidate while the denominator was Math.min(5, candidates.length),
  // so 8 hits among 20 datasets rendered as "8 out of 5 top datasets".
  //
  // The wording is hedged because the backend field is `maybe_has_survival_data`,
  // a heuristic over study metadata. Stating it as fact sends someone to download
  // a dataset expecting clinical outcomes that may not be there.
  const considered = analysisData.datasetDetails.length;
  const survivalDataCount = analysisData.datasetDetails.filter(
    d => d.maybeHasSurvivalData,
  ).length;
  const survivalText = survivalDataCount > 0
    ? `**Survival data**: ${survivalDataCount} of ${considered} dataset${considered === 1 ? '' : 's'} may include clinical survival information (inferred from study metadata; confirm against the series record)`
    : '**Survival data**: none of the datasets examined appear to include clinical survival information';

  // Extract common themes from match reasons
  const matchReasons = candidates.slice(0, 3).flatMap(c => c.matchReasons || []);
  const uniqueReasons = [...new Set(matchReasons)].slice(0, 3);
  const reasonsText = uniqueReasons.length > 0
    ? `\n\n**Key Match Criteria:**\n${uniqueReasons.map(r => `- ${r}`).join('\n')}`
    : '';

  return `I found **${candidates.length}** datasets in the GEO database matching your query.

**Dataset Summary:**
- Total samples analyzed: **${totalSamples} samples**
- Organism: ${analysisData.organisms}
- Primary platforms: ${analysisData.platform}
- ${survivalText}${reasonsText}

The top results include datasets with comprehensive metadata and experimental details. Click on any dataset to view more information.`;
}
