/**
 * Preferences API Client
 *
 * Provides methods for interacting with the backend user preferences API.
 * Handles preference CRUD operations, suggestions, and acceptance workflow.
 */

import { getAnonUserId } from "../lib/anonUser";
import type {
  PreferenceResponse,
  PreferenceCreateRequest,
  PreferenceUpdateRequest,
  UserPreferencesResponse,
  PreferenceSuggestionsResponse,
  AcceptSuggestionRequest,
} from '@/types/preferences';

import { API_BASE_URL } from '@/lib/apiBaseUrl';

/**
 * Error class for Preferences API errors
 */
export class PreferencesApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: any
  ) {
    super(message);
    this.name = 'PreferencesApiError';
  }
}

/**
 * Fetch wrapper with error handling
 */
async function fetchWithErrorHandling<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': getAnonUserId(),
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new PreferencesApiError(
        errorData.detail || `Request failed with status ${response.status}`,
        response.status,
        errorData
      );
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (error) {
    if (error instanceof PreferencesApiError) {
      throw error;
    }

    if (error instanceof TypeError) {
      throw new PreferencesApiError('Network error: Unable to reach the server');
    }

    throw new PreferencesApiError(
      error instanceof Error ? error.message : 'Unknown error occurred'
    );
  }
}

/**
 * Preferences API Client Class
 */
export class PreferencesApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get all preferences for a user
   */
  async getUserPreferences(userId: string): Promise<UserPreferencesResponse> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/preferences`;
    return await fetchWithErrorHandling<UserPreferencesResponse>(url);
  }

  /**
   * Create a new preference
   */
  async createPreference(
    userId: string,
    request: PreferenceCreateRequest
  ): Promise<PreferenceResponse> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/preferences`;
    return await fetchWithErrorHandling<PreferenceResponse>(url, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Update an existing preference
   */
  async updatePreference(
    userId: string,
    preferenceId: string,
    request: PreferenceUpdateRequest
  ): Promise<PreferenceResponse> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/preferences/${preferenceId}`;
    return await fetchWithErrorHandling<PreferenceResponse>(url, {
      method: 'PUT',
      body: JSON.stringify(request),
    });
  }

  /**
   * Delete a preference
   */
  async deletePreference(userId: string, preferenceId: string): Promise<void> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/preferences/${preferenceId}`;
    await fetchWithErrorHandling<void>(url, {
      method: 'DELETE',
    });
  }

  /**
   * Get preference suggestions based on user's search history
   */
  async getSuggestions(
    userId: string,
    minSearches: number = 5
  ): Promise<PreferenceSuggestionsResponse> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/preferences/suggestions?min_searches=${minSearches}`;
    return await fetchWithErrorHandling<PreferenceSuggestionsResponse>(url);
  }

  /**
   * Accept a preference suggestion
   */
  async acceptSuggestion(
    userId: string,
    request: AcceptSuggestionRequest
  ): Promise<PreferenceResponse> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/preferences/accept`;
    return await fetchWithErrorHandling<PreferenceResponse>(url, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Bulk update preferences (convenience method)
   */
  async updatePreferences(
    userId: string,
    preferences: Array<{ id?: string; type: string; value: Record<string, any>; confidence?: number }>
  ): Promise<PreferenceResponse[]> {
    const results: PreferenceResponse[] = [];

    for (const pref of preferences) {
      if (pref.id) {
        // Update existing preference
        const updated = await this.updatePreference(userId, pref.id, {
          preferenceValue: pref.value,
          confidenceScore: pref.confidence,
        });
        results.push(updated);
      } else {
        // Create new preference
        const created = await this.createPreference(userId, {
          preferenceType: pref.type,
          preferenceValue: pref.value,
          confidenceScore: pref.confidence,
        });
        results.push(created);
      }
    }

    return results;
  }
}

// Export singleton instance
export const preferencesApi = new PreferencesApiClient();

// Export helper functions for common operations
export const preferencesApiHelpers = {
  /**
   * Accept suggestion with automatic error handling
   */
  async acceptSuggestionSafely(
    userId: string,
    suggestion: AcceptSuggestionRequest
  ): Promise<PreferenceResponse | null> {
    try {
      return await preferencesApi.acceptSuggestion(userId, suggestion);
    } catch (error) {
      console.error('Failed to accept suggestion:', error);
      return null;
    }
  },

  /**
   * Delete preference with automatic error handling
   */
  async deletePreferenceSafely(
    userId: string,
    preferenceId: string
  ): Promise<boolean> {
    try {
      await preferencesApi.deletePreference(userId, preferenceId);
      return true;
    } catch (error) {
      console.error('Failed to delete preference:', error);
      return false;
    }
  },

  /**
   * Get suggestions with fallback
   */
  async getSuggestionsSafely(
    userId: string,
    minSearches: number = 5
  ): Promise<PreferenceSuggestionsResponse> {
    try {
      return await preferencesApi.getSuggestions(userId, minSearches);
    } catch (error) {
      console.error('Failed to get suggestions:', error);
      return { suggestions: [], total: 0 };
    }
  },
};
