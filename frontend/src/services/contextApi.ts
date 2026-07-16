/**
 * Context API Client
 *
 * Provides methods for interacting with the backend context persistence API.
 * Handles conversation context, search results, and user interactions.
 */

import type {
  ConversationContext,
  SaveConversationRequest,
  SaveSearchRequest,
  TrackInteractionRequest,
  DatasetHistory,
  UserContextSummary,
  RecalledDataset,
  Message,
  Search,
  UserInteraction,
} from '@/types/context';
import { getAnonUserId } from '@/lib/anonUser';

const API_BASE_URL = import.meta.env.VITE_GEO_API_URL || 'http://localhost:8000';

/**
 * Error class for Context API errors
 */
export class ContextApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: any
  ) {
    super(message);
    this.name = 'ContextApiError';
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
      throw new ContextApiError(
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
    if (error instanceof ContextApiError) {
      throw error;
    }

    if (error instanceof TypeError) {
      throw new ContextApiError('Network error: Unable to reach the server');
    }

    throw new ContextApiError(
      error instanceof Error ? error.message : 'Unknown error occurred'
    );
  }
}

/**
 * Context API Client Class
 */
export class ContextApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get full conversation context
   */
  async getConversationContext(
    conversationId: string,
    useCache: boolean = true
  ): Promise<ConversationContext | null> {
    try {
      const url = `${this.baseUrl}/api/v1/conversations/${conversationId}?use_cache=${useCache}`;
      return await fetchWithErrorHandling<ConversationContext>(url);
    } catch (error) {
      if (error instanceof ContextApiError && error.statusCode === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Restore complete conversation state (includes search results)
   */
  async restoreConversationState(
    conversationId: string
  ): Promise<ConversationContext | null> {
    try {
      const url = `${this.baseUrl}/api/v1/conversations/${conversationId}/context`;
      return await fetchWithErrorHandling<ConversationContext>(url);
    } catch (error) {
      if (error instanceof ContextApiError && error.statusCode === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Create or update a conversation with messages
   */
  async saveConversation(
    request: SaveConversationRequest
  ): Promise<{ conversation_id: string; message_count: number }> {
    const url = `${this.baseUrl}/api/v1/conversations`;
    return await fetchWithErrorHandling(url, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Add a message to an existing conversation
   */
  async addMessage(
    conversationId: string,
    role: 'user' | 'assistant' | 'system',
    content: string,
    metadata?: Record<string, any>
  ): Promise<Message> {
    const url = `${this.baseUrl}/api/v1/conversations/${conversationId}/messages`;
    return await fetchWithErrorHandling(url, {
      method: 'POST',
      body: JSON.stringify({ role, content, metadata }),
    });
  }

  /**
   * Save a search with its results
   */
  async saveSearch(request: SaveSearchRequest): Promise<Search> {
    const url = `${this.baseUrl}/context/searches`;
    return await fetchWithErrorHandling(url, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Track a dataset interaction
   */
  async trackInteraction(
    request: TrackInteractionRequest
  ): Promise<UserInteraction> {
    const url = `${this.baseUrl}/context/interactions`;
    return await fetchWithErrorHandling(url, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Get dataset interaction history for a user
   */
  async getDatasetHistory(
    datasetId: string,
    userId: string
  ): Promise<DatasetHistory> {
    const url = `${this.baseUrl}/context/datasets/${datasetId}/history?user_id=${userId}`;
    return await fetchWithErrorHandling(url);
  }

  /**
   * Get user's context summary (stats and recent activity)
   */
  async getUserContextSummary(userId: string): Promise<UserContextSummary> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/summary`;
    return await fetchWithErrorHandling(url);
  }

  /**
   * List user's conversations
   */
  async listUserConversations(
    userId: string,
    limit: number = 50,
    includeArchived: boolean = false
  ): Promise<ConversationContext[]> {
    const url = `${this.baseUrl}/api/v1/users/${userId}/conversations?limit=${limit}&include_archived=${includeArchived}`;
    return await fetchWithErrorHandling(url);
  }

  /**
   * Archive a conversation
   */
  async archiveConversation(conversationId: string): Promise<void> {
    const url = `${this.baseUrl}/api/v1/conversations/${conversationId}/archive`;
    await fetchWithErrorHandling(url, { method: 'POST' });
  }

  /**
   * Delete a conversation
   */
  async deleteConversation(conversationId: string): Promise<void> {
    const url = `${this.baseUrl}/api/v1/conversations/${conversationId}`;
    await fetchWithErrorHandling(url, { method: 'DELETE' });
  }

  /**
   * Get legacy context endpoint (for backward compatibility)
   * This is the existing /geo/context/{conversation_id} endpoint
   */
  async getLegacyContext(conversationId: string): Promise<any> {
    try {
      const url = `${this.baseUrl}/geo/context/${conversationId}`;
      return await fetchWithErrorHandling(url);
    } catch (error) {
      if (error instanceof ContextApiError && error.statusCode === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Get user's recalled datasets (recently viewed/interacted with)
   */
  async getRecalledDatasets(
    userId: string,
    limit: number = 20
  ): Promise<RecalledDataset[]> {
    const url = `${this.baseUrl}/api/v1/datasets/recalled?user_id=${userId}&limit=${limit}`;
    return await fetchWithErrorHandling(url);
  }

  /**
   * Get conversations that reference a specific dataset
   */
  async getDatasetConversations(
    datasetId: string,
    userId: string
  ): Promise<ConversationContext[]> {
    const url = `${this.baseUrl}/api/v1/datasets/${datasetId}/conversations?user_id=${userId}`;
    return await fetchWithErrorHandling(url);
  }
}

// Export singleton instance
export const contextApi = new ContextApiClient();

// Export helper functions for common operations
export const contextApiHelpers = {
  /**
   * Save conversation with automatic error handling and retry
   */
  async saveConversationSafely(
    request: SaveConversationRequest,
    maxRetries: number = 2
  ): Promise<boolean> {
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        await contextApi.saveConversation(request);
        return true;
      } catch (error) {
        console.error(`Failed to save conversation (attempt ${attempt + 1}/${maxRetries + 1}):`, error);

        if (attempt === maxRetries) {
          // Final attempt failed, save to localStorage as backup
          try {
            const backupKey = `conversation_backup_${request.user_id}_${Date.now()}`;
            localStorage.setItem(backupKey, JSON.stringify(request));
            console.warn('Saved conversation to localStorage backup:', backupKey);
          } catch (e) {
            console.error('Failed to save backup to localStorage:', e);
          }
          return false;
        }

        // Wait before retry (exponential backoff)
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
      }
    }
    return false;
  },

  /**
   * Track interaction with automatic fallback
   */
  async trackInteractionSafely(
    request: TrackInteractionRequest
  ): Promise<boolean> {
    try {
      await contextApi.trackInteraction(request);
      return true;
    } catch (error) {
      console.error('Failed to track interaction:', error);

      // Store in localStorage for later sync
      try {
        const pendingKey = 'pending_interactions';
        const pending = JSON.parse(localStorage.getItem(pendingKey) || '[]');
        pending.push({ ...request, timestamp: new Date().toISOString() });
        localStorage.setItem(pendingKey, JSON.stringify(pending));
      } catch (e) {
        console.error('Failed to queue pending interaction:', e);
      }

      return false;
    }
  },

  /**
   * Restore conversation with localStorage fallback
   */
  async restoreConversationWithFallback(
    conversationId: string
  ): Promise<ConversationContext | null> {
    try {
      // Try to restore from backend
      const context = await contextApi.restoreConversationState(conversationId);
      if (context) {
        return context;
      }
    } catch (error) {
      console.error('Failed to restore from backend:', error);
    }

    // Fallback to localStorage
    try {
      const localKey = `conversation_${conversationId}`;
      const localData = localStorage.getItem(localKey);
      if (localData) {
        console.warn('Using localStorage fallback for conversation:', conversationId);
        return JSON.parse(localData);
      }
    } catch (error) {
      console.error('Failed to restore from localStorage:', error);
    }

    return null;
  },
};
