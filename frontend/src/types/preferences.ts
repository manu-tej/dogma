/**
 * TypeScript types for User Preferences API
 *
 * These types match the backend Pydantic schemas from:
 * src/quration/api/schemas/preferences.py
 */

export interface PreferenceResponse {
  id: string;
  userId: string;
  preferenceType: string;
  preferenceValue: Record<string, any>;
  confidenceScore?: number;
  createdAt: string;
  updatedAt: string;
}

export interface PreferenceCreateRequest {
  preferenceType: string;
  preferenceValue: Record<string, any>;
  confidenceScore?: number;
}

export interface PreferenceUpdateRequest {
  preferenceValue?: Record<string, any>;
  confidenceScore?: number;
}

export interface UserPreferencesResponse {
  preferences: PreferenceResponse[];
  total: number;
}

export interface PreferencesByTypeResponse {
  organism: PreferenceResponse[];
  platform: PreferenceResponse[];
  diseaseArea: PreferenceResponse[];
  other: PreferenceResponse[];
}

export interface PreferenceSuggestion {
  preferenceType: string;
  preferenceValue: Record<string, any>;
  confidenceScore: number;
  rationale: string;
  basedOnSearches: number;
}

export interface PreferenceSuggestionsResponse {
  suggestions: PreferenceSuggestion[];
  total: number;
}

export interface AcceptSuggestionRequest {
  preferenceType: string;
  preferenceValue: Record<string, any>;
  confidenceScore: number;
}

/**
 * Local state types for UI
 */
export interface PreferencesLoadingState {
  isLoading: boolean;
  isSaving: boolean;
  error?: string;
}
