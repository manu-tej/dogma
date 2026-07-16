/**
 * Auto-Preferences Hook
 *
 * Manages automatic application of user preferences to search queries.
 * Handles confidence-based filtering, application state tracking, and override controls.
 */

import { useState, useCallback, useMemo } from 'react';
import type { PreferenceResponse } from '@/types/preferences';
import type { QuerySpec } from '@/lib/geo-client';
import {
  mergePreferencesWithQuery,
  filterByConfidence,
  wouldPreferencesModifyQuery,
  DEFAULT_CONFIDENCE_THRESHOLD,
} from '@/utils/preferenceApplicator';

interface UseAutoPreferencesOptions {
  preferences: PreferenceResponse[];
  isEnabled?: boolean;
  confidenceThreshold?: number;
}

interface UseAutoPreferencesReturn {
  // State
  applicablePreferences: PreferenceResponse[];
  appliedPreferenceIds: Set<string>;
  isApplying: boolean;
  confidenceThreshold: number;

  // Actions
  applyPreferences: (querySpec: QuerySpec) => QuerySpec;
  clearPreferences: () => void;
  setConfidenceThreshold: (threshold: number) => void;
  wouldModifyQuery: (querySpec: QuerySpec) => boolean;

  // Metadata
  applicableCount: number;
  totalCount: number;
}

/**
 * Hook for automatic preference application to search queries
 *
 * Provides automatic filtering, application, and tracking of user preferences
 * with confidence-based controls.
 *
 * @param options - Configuration options
 * @returns Auto-preference state and actions
 *
 * @example
 * const {
 *   applicablePreferences,
 *   applyPreferences,
 *   wouldModifyQuery,
 * } = useAutoPreferences({
 *   preferences,
 *   isEnabled: true,
 *   confidenceThreshold: 0.7,
 * });
 *
 * // Before executing search
 * if (isEnabled && wouldModifyQuery(querySpec)) {
 *   const mergedQuery = applyPreferences(querySpec);
 *   executeSearch(mergedQuery);
 * }
 */
export function useAutoPreferences(
  options: UseAutoPreferencesOptions
): UseAutoPreferencesReturn {
  const {
    preferences,
    isEnabled = true,
    confidenceThreshold: initialThreshold = DEFAULT_CONFIDENCE_THRESHOLD,
  } = options;

  // State
  const [appliedPreferenceIds, setAppliedPreferenceIds] = useState<Set<string>>(
    new Set()
  );
  const [isApplying, setIsApplying] = useState(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState(initialThreshold);

  /**
   * Get preferences that meet confidence threshold
   */
  const applicablePreferences = useMemo(() => {
    if (!isEnabled) {
      return [];
    }

    return filterByConfidence(preferences, confidenceThreshold);
  }, [preferences, confidenceThreshold, isEnabled]);

  /**
   * Apply preferences to a query specification
   */
  const applyPreferences = useCallback(
    (querySpec: QuerySpec): QuerySpec => {
      if (!isEnabled || applicablePreferences.length === 0) {
        return querySpec;
      }

      setIsApplying(true);

      try {
        // Merge preferences with query
        const mergedQuery = mergePreferencesWithQuery(
          querySpec,
          applicablePreferences,
          confidenceThreshold
        );

        // Track which preferences were applied
        const appliedIds = new Set(applicablePreferences.map((p) => p.id));
        setAppliedPreferenceIds(appliedIds);

        console.log(
          '[useAutoPreferences] Applied',
          appliedIds.size,
          'preferences to query'
        );

        return mergedQuery;
      } finally {
        setIsApplying(false);
      }
    },
    [isEnabled, applicablePreferences, confidenceThreshold]
  );

  /**
   * Clear applied preferences tracking
   */
  const clearPreferences = useCallback(() => {
    setAppliedPreferenceIds(new Set());
    console.log('[useAutoPreferences] Cleared applied preferences');
  }, []);

  /**
   * Check if preferences would modify a query
   */
  const wouldModifyQuery = useCallback(
    (querySpec: QuerySpec): boolean => {
      if (!isEnabled || applicablePreferences.length === 0) {
        return false;
      }

      return wouldPreferencesModifyQuery(
        querySpec,
        applicablePreferences,
        confidenceThreshold
      );
    },
    [isEnabled, applicablePreferences, confidenceThreshold]
  );

  return {
    // State
    applicablePreferences,
    appliedPreferenceIds,
    isApplying,
    confidenceThreshold,

    // Actions
    applyPreferences,
    clearPreferences,
    setConfidenceThreshold,
    wouldModifyQuery,

    // Metadata
    applicableCount: applicablePreferences.length,
    totalCount: preferences.length,
  };
}
