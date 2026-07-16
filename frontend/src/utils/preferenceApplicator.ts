/**
 * Preference Applicator Utility
 *
 * Handles merging user preferences with search queries.
 * Provides confidence-based filtering and preference conflict resolution.
 */

import type { PreferenceResponse } from '@/types/preferences';
import type { QuerySpec } from '@/lib/geo-client';

/**
 * Default confidence threshold for applying preferences
 */
export const DEFAULT_CONFIDENCE_THRESHOLD = 0.7;

/**
 * Filter preferences by confidence score
 *
 * @param preferences - User preferences to filter
 * @param threshold - Minimum confidence score (0.0 to 1.0)
 * @returns Preferences that meet or exceed the confidence threshold
 */
export function filterByConfidence(
  preferences: PreferenceResponse[],
  threshold: number = DEFAULT_CONFIDENCE_THRESHOLD
): PreferenceResponse[] {
  return preferences.filter(
    (pref) => (pref.confidenceScore ?? 0) >= threshold
  );
}

/**
 * Build preference query parameters from preferences
 *
 * Converts preference objects into queryable terms that can be merged
 * into a QuerySpec.
 *
 * @param preferences - User preferences to convert
 * @returns Object containing arrays of terms extracted from preferences
 */
export function buildPreferenceQuery(preferences: PreferenceResponse[]): {
  diseaseTerms: string[];
  therapyClasses: string[];
  genes: string[];
  keywords: string[];
  organisms: string[];
  platforms: string[];
} {
  const result = {
    diseaseTerms: [] as string[],
    therapyClasses: [] as string[],
    genes: [] as string[],
    keywords: [] as string[],
    organisms: [] as string[],
    platforms: [] as string[],
  };

  for (const pref of preferences) {
    const { preferenceType, preferenceValue } = pref;

    // Extract preferred values from preference
    const preferred = preferenceValue?.preferred;
    if (!preferred || !Array.isArray(preferred)) {
      continue;
    }

    // Map preference types to query fields
    switch (preferenceType.toLowerCase()) {
      case 'disease':
      case 'disease_area':
      case 'diseasearea':
        result.diseaseTerms.push(...preferred);
        break;

      case 'therapy':
      case 'therapy_class':
      case 'therapyclass':
        result.therapyClasses.push(...preferred);
        break;

      case 'gene':
      case 'target':
      case 'genes':
      case 'targets':
        result.genes.push(...preferred);
        break;

      case 'organism':
        result.organisms.push(...preferred);
        break;

      case 'platform':
        result.platforms.push(...preferred);
        break;

      case 'keyword':
      case 'keywords':
        result.keywords.push(...preferred);
        break;

      default:
        // Unknown preference type - add to keywords as fallback
        result.keywords.push(...preferred);
    }
  }

  return result;
}

/**
 * Merge user preferences with a query specification
 *
 * Combines user-defined preferences with an explicit search query.
 * User query takes precedence over preferences when conflicts occur.
 *
 * @param querySpec - The base query specification from user input
 * @param preferences - User preferences to merge
 * @param confidenceThreshold - Minimum confidence score (default: 0.7)
 * @returns Merged QuerySpec with preferences applied
 *
 * @example
 * const query = parseNaturalLanguageQuery("melanoma checkpoint inhibitor");
 * const preferences = [
 *   { preferenceType: "organism", preferenceValue: { preferred: ["Homo sapiens"] }, confidenceScore: 0.9 }
 * ];
 * const merged = mergePreferencesWithQuery(query, preferences);
 * // merged.studyKeywords will include "Homo sapiens"
 */
export function mergePreferencesWithQuery(
  querySpec: QuerySpec,
  preferences: PreferenceResponse[],
  confidenceThreshold: number = DEFAULT_CONFIDENCE_THRESHOLD
): QuerySpec {
  // Start with the base query spec
  const merged: QuerySpec = { ...querySpec };

  // Filter preferences by confidence threshold
  const applicablePrefs = filterByConfidence(preferences, confidenceThreshold);

  if (applicablePrefs.length === 0) {
    return merged;
  }

  // Build preference query terms
  const prefQuery = buildPreferenceQuery(applicablePrefs);

  // Merge disease terms (user query takes precedence - no duplicates)
  if (prefQuery.diseaseTerms.length > 0) {
    const existingTerms = new Set(
      (merged.diseaseTerms || []).map((t) => t.toLowerCase())
    );
    const newTerms = prefQuery.diseaseTerms.filter(
      (t) => !existingTerms.has(t.toLowerCase())
    );
    merged.diseaseTerms = [...(merged.diseaseTerms || []), ...newTerms];
  }

  // Merge therapy class (only add if not already specified)
  if (!merged.therapyClass && prefQuery.therapyClasses.length > 0) {
    // Use first therapy class preference
    merged.therapyClass = prefQuery.therapyClasses[0];
  }

  // Merge genes/targets (no duplicates)
  if (prefQuery.genes.length > 0) {
    const existingGenes = new Set(
      (merged.targetsOrGenes || []).map((g) => g.toUpperCase())
    );
    const newGenes = prefQuery.genes.filter(
      (g) => !existingGenes.has(g.toUpperCase())
    );
    merged.targetsOrGenes = [...(merged.targetsOrGenes || []), ...newGenes];
  }

  // Merge keywords (organisms, platforms, and other keywords)
  const additionalKeywords = [
    ...prefQuery.organisms,
    ...prefQuery.platforms,
    ...prefQuery.keywords,
  ];

  if (additionalKeywords.length > 0) {
    const existingKeywords = new Set(
      (merged.studyKeywords || []).map((k) => k.toLowerCase())
    );
    const newKeywords = additionalKeywords.filter(
      (k) => !existingKeywords.has(k.toLowerCase())
    );
    merged.studyKeywords = [...(merged.studyKeywords || []), ...newKeywords];
  }

  return merged;
}

/**
 * Get human-readable summary of applied preferences
 *
 * @param preferences - Preferences to summarize
 * @param confidenceThreshold - Minimum confidence score
 * @returns Array of readable preference descriptions
 */
export function getAppliedPreferencesSummary(
  preferences: PreferenceResponse[],
  confidenceThreshold: number = DEFAULT_CONFIDENCE_THRESHOLD
): string[] {
  const applicable = filterByConfidence(preferences, confidenceThreshold);
  const summary: string[] = [];

  for (const pref of applicable) {
    const preferred = pref.preferenceValue?.preferred;
    if (!preferred || !Array.isArray(preferred) || preferred.length === 0) {
      continue;
    }

    const values = preferred.join(', ');
    const confidence = Math.round((pref.confidenceScore ?? 0) * 100);

    summary.push(
      `${pref.preferenceType}: ${values} (${confidence}% confidence)`
    );
  }

  return summary;
}

/**
 * Check if preferences would modify a query
 *
 * @param querySpec - Query to check
 * @param preferences - Preferences to apply
 * @param confidenceThreshold - Minimum confidence score
 * @returns True if preferences would add any new terms
 */
export function wouldPreferencesModifyQuery(
  querySpec: QuerySpec,
  preferences: PreferenceResponse[],
  confidenceThreshold: number = DEFAULT_CONFIDENCE_THRESHOLD
): boolean {
  const applicable = filterByConfidence(preferences, confidenceThreshold);

  if (applicable.length === 0) {
    return false;
  }

  const prefQuery = buildPreferenceQuery(applicable);

  // Check if any preference terms would be added
  const existingTerms = new Set([
    ...(querySpec.diseaseTerms || []).map((t) => t.toLowerCase()),
    ...(querySpec.targetsOrGenes || []).map((g) => g.toUpperCase()),
    ...(querySpec.studyKeywords || []).map((k) => k.toLowerCase()),
  ]);

  const hasNewTerms = [
    ...prefQuery.diseaseTerms,
    ...prefQuery.genes,
    ...prefQuery.organisms,
    ...prefQuery.platforms,
    ...prefQuery.keywords,
  ].some((term) => !existingTerms.has(term.toLowerCase()));

  const hasTherapyClass = !querySpec.therapyClass && prefQuery.therapyClasses.length > 0;

  return hasNewTerms || hasTherapyClass;
}
