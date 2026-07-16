/**
 * Custom hook for managing user preferences
 *
 * Provides automatic fetching, state management, and actions for user preferences.
 * Handles suggestion acceptance workflow, CRUD operations, and error handling.
 */

import { useState, useEffect, useCallback } from 'react';
import type {
  PreferenceResponse,
  PreferenceSuggestion,
  PreferencesLoadingState,
  PreferenceCreateRequest,
  PreferenceUpdateRequest,
} from '@/types/preferences';
import { preferencesApi, preferencesApiHelpers } from '@/services/preferencesApi';

interface UseUserPreferencesOptions {
  userId: string;
  autoFetch?: boolean;
  fetchSuggestions?: boolean;
  minSearchesForSuggestion?: number;
}

interface UseUserPreferencesReturn {
  // State
  preferences: PreferenceResponse[];
  suggestions: PreferenceSuggestion[];
  loadingState: PreferencesLoadingState;

  // Actions
  refreshPreferences: () => Promise<void>;
  createPreference: (request: PreferenceCreateRequest) => Promise<PreferenceResponse | null>;
  updatePreference: (preferenceId: string, request: PreferenceUpdateRequest) => Promise<PreferenceResponse | null>;
  deletePreference: (preferenceId: string) => Promise<boolean>;
  acceptSuggestion: (suggestion: PreferenceSuggestion) => Promise<PreferenceResponse | null>;
  rejectSuggestion: (suggestion: PreferenceSuggestion) => void;
  fetchSuggestions: () => Promise<void>;
}

/**
 * Hook for managing user preferences with automatic fetching and state management
 */
export function useUserPreferences(
  options: UseUserPreferencesOptions
): UseUserPreferencesReturn {
  const {
    userId,
    autoFetch = true,
    fetchSuggestions: autoFetchSuggestions = false,
    minSearchesForSuggestion = 5,
  } = options;

  // State
  const [preferences, setPreferences] = useState<PreferenceResponse[]>([]);
  const [suggestions, setSuggestions] = useState<PreferenceSuggestion[]>([]);
  const [loadingState, setLoadingState] = useState<PreferencesLoadingState>({
    isLoading: false,
    isSaving: false,
  });

  /**
   * Fetch user preferences from API
   */
  const refreshPreferences = useCallback(async () => {
    if (!userId) {
      return;
    }

    setLoadingState(prev => ({ ...prev, isLoading: true, error: undefined }));

    try {
      const response = await preferencesApi.getUserPreferences(userId);
      setPreferences(response.preferences);
      console.log('[useUserPreferences] Loaded', response.total, 'preferences');
    } catch (error) {
      console.error('[useUserPreferences] Failed to fetch preferences:', error);
      setLoadingState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load preferences',
      }));
    } finally {
      setLoadingState(prev => ({ ...prev, isLoading: false }));
    }
  }, [userId]);

  /**
   * Fetch preference suggestions
   */
  const fetchSuggestions = useCallback(async () => {
    if (!userId) {
      return;
    }

    try {
      const response = await preferencesApiHelpers.getSuggestionsSafely(
        userId,
        minSearchesForSuggestion
      );
      setSuggestions(response.suggestions);
      console.log('[useUserPreferences] Loaded', response.total, 'suggestions');
    } catch (error) {
      console.error('[useUserPreferences] Failed to fetch suggestions:', error);
    }
  }, [userId, minSearchesForSuggestion]);

  /**
   * Create a new preference
   */
  const createPreference = useCallback(
    async (request: PreferenceCreateRequest): Promise<PreferenceResponse | null> => {
      if (!userId) {
        return null;
      }

      setLoadingState(prev => ({ ...prev, isSaving: true, error: undefined }));

      try {
        const newPreference = await preferencesApi.createPreference(userId, request);
        setPreferences(prev => [...prev, newPreference]);
        console.log('[useUserPreferences] Created preference:', newPreference.id);
        return newPreference;
      } catch (error) {
        console.error('[useUserPreferences] Failed to create preference:', error);
        setLoadingState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to create preference',
        }));
        return null;
      } finally {
        setLoadingState(prev => ({ ...prev, isSaving: false }));
      }
    },
    [userId]
  );

  /**
   * Update an existing preference
   */
  const updatePreference = useCallback(
    async (
      preferenceId: string,
      request: PreferenceUpdateRequest
    ): Promise<PreferenceResponse | null> => {
      if (!userId) {
        return null;
      }

      setLoadingState(prev => ({ ...prev, isSaving: true, error: undefined }));

      try {
        const updated = await preferencesApi.updatePreference(userId, preferenceId, request);
        setPreferences(prev =>
          prev.map(p => (p.id === preferenceId ? updated : p))
        );
        console.log('[useUserPreferences] Updated preference:', preferenceId);
        return updated;
      } catch (error) {
        console.error('[useUserPreferences] Failed to update preference:', error);
        setLoadingState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to update preference',
        }));
        return null;
      } finally {
        setLoadingState(prev => ({ ...prev, isSaving: false }));
      }
    },
    [userId]
  );

  /**
   * Delete a preference
   */
  const deletePreference = useCallback(
    async (preferenceId: string): Promise<boolean> => {
      if (!userId) {
        return false;
      }

      setLoadingState(prev => ({ ...prev, isSaving: true, error: undefined }));

      try {
        const success = await preferencesApiHelpers.deletePreferenceSafely(
          userId,
          preferenceId
        );

        if (success) {
          setPreferences(prev => prev.filter(p => p.id !== preferenceId));
          console.log('[useUserPreferences] Deleted preference:', preferenceId);
        }

        return success;
      } catch (error) {
        console.error('[useUserPreferences] Failed to delete preference:', error);
        setLoadingState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to delete preference',
        }));
        return false;
      } finally {
        setLoadingState(prev => ({ ...prev, isSaving: false }));
      }
    },
    [userId]
  );

  /**
   * Accept a preference suggestion
   */
  const acceptSuggestion = useCallback(
    async (suggestion: PreferenceSuggestion): Promise<PreferenceResponse | null> => {
      if (!userId) {
        return null;
      }

      setLoadingState(prev => ({ ...prev, isSaving: true, error: undefined }));

      try {
        const newPreference = await preferencesApiHelpers.acceptSuggestionSafely(userId, {
          preferenceType: suggestion.preferenceType,
          preferenceValue: suggestion.preferenceValue,
          confidenceScore: suggestion.confidenceScore,
        });

        if (newPreference) {
          setPreferences(prev => [...prev, newPreference]);
          // Remove accepted suggestion from suggestions list
          setSuggestions(prev =>
            prev.filter(s => s.preferenceType !== suggestion.preferenceType)
          );
          console.log('[useUserPreferences] Accepted suggestion:', suggestion.preferenceType);
        }

        return newPreference;
      } catch (error) {
        console.error('[useUserPreferences] Failed to accept suggestion:', error);
        setLoadingState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to accept suggestion',
        }));
        return null;
      } finally {
        setLoadingState(prev => ({ ...prev, isSaving: false }));
      }
    },
    [userId]
  );

  /**
   * Reject a suggestion (local state only)
   */
  const rejectSuggestion = useCallback((suggestion: PreferenceSuggestion) => {
    setSuggestions(prev =>
      prev.filter(s => s.preferenceType !== suggestion.preferenceType)
    );
    console.log('[useUserPreferences] Rejected suggestion:', suggestion.preferenceType);
  }, []);

  /**
   * Auto-fetch preferences on mount
   */
  useEffect(() => {
    if (autoFetch && userId) {
      refreshPreferences();
    }
  }, [autoFetch, userId, refreshPreferences]);

  /**
   * Auto-fetch suggestions if enabled
   */
  useEffect(() => {
    if (autoFetchSuggestions && userId) {
      fetchSuggestions();
    }
  }, [autoFetchSuggestions, userId, fetchSuggestions]);

  return {
    preferences,
    suggestions,
    loadingState,
    refreshPreferences,
    createPreference,
    updatePreference,
    deletePreference,
    acceptSuggestion,
    rejectSuggestion,
    fetchSuggestions,
  };
}
