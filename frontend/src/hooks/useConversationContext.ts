/**
 * Custom hook for managing conversation context
 *
 * Provides automatic context restoration, persistence, and synchronization
 * with the backend API and localStorage fallback.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  Message,
  ConversationContext,
  ContextLoadingState,
  Search,
} from '@/types/context';
import { contextApi, contextApiHelpers } from '@/services/contextApi';
import type { GeoDatasetCandidate } from '@/lib/geo-client';

interface UseConversationContextOptions {
  conversationId: string | null;
  userId: string;
  autoSave?: boolean;
  autoSaveDelay?: number;
  enableLocalStorageFallback?: boolean;
}

interface UseConversationContextReturn {
  // State
  messages: Message[];
  searchResults: GeoDatasetCandidate[] | null;
  loadingState: ContextLoadingState;
  context: ConversationContext | null;

  // Actions
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  saveSearchResults: (results: GeoDatasetCandidate[], querySpec: any) => Promise<void>;
  trackDatasetInteraction: (
    datasetId: string,
    interactionType: 'view' | 'analyze' | 'download',
    metadata?: Record<string, any>
  ) => Promise<void>;
  restoreContext: () => Promise<void>;
  saveContext: () => Promise<void>;
  clearContext: () => void;
}

/**
 * Hook for managing conversation context with automatic persistence
 */
export function useConversationContext(
  options: UseConversationContextOptions
): UseConversationContextReturn {
  const {
    conversationId,
    userId,
    autoSave = true,
    autoSaveDelay = 2000,
    enableLocalStorageFallback = true,
  } = options;

  // State
  const [messages, setMessages] = useState<Message[]>([]);
  const [searchResults, setSearchResults] = useState<GeoDatasetCandidate[] | null>(null);
  const [context, setContext] = useState<ConversationContext | null>(null);
  const [loadingState, setLoadingState] = useState<ContextLoadingState>({
    isLoading: false,
    isRestoring: false,
    isSaving: false,
  });

  // Refs for tracking state
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isRestoringRef = useRef(false);
  const lastSavedMessagesRef = useRef<string>('');

  /**
   * Restore conversation context from backend or localStorage
   */
  const restoreContext = useCallback(async () => {
    if (!conversationId || isRestoringRef.current) {
      return;
    }

    isRestoringRef.current = true;
    setLoadingState(prev => ({ ...prev, isRestoring: true, error: undefined }));

    try {
      console.log('[useConversationContext] Restoring context for:', conversationId);

      // Try backend first
      let restoredContext: ConversationContext | null = null;

      try {
        restoredContext = await contextApi.restoreConversationState(conversationId);
      } catch (error) {
        console.warn('[useConversationContext] Backend restore failed:', error);

        // Try legacy endpoint
        if (enableLocalStorageFallback) {
          try {
            const legacyContext = await contextApi.getLegacyContext(conversationId);
            if (legacyContext) {
              console.log('[useConversationContext] Using legacy context');
              setSearchResults(legacyContext.results || null);
            }
          } catch (legacyError) {
            console.warn('[useConversationContext] Legacy context not found');
          }
        }
      }

      if (restoredContext) {
        console.log('[useConversationContext] Restored context:', {
          messages: restoredContext.messages.length,
          searches: restoredContext.searches.length,
          interactions: restoredContext.interactions.length,
        });

        // Convert message timestamps from strings to Date objects
        const messagesWithDates: Message[] = restoredContext.messages.map(msg => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }));

        setMessages(messagesWithDates);
        setContext(restoredContext);

        // Restore latest search results if available
        if (restoredContext.searches.length > 0) {
          const latestSearch = restoredContext.searches[restoredContext.searches.length - 1];
          if (latestSearch.results) {
            setSearchResults(latestSearch.results as any);
          }
        }

        // Update last saved state
        lastSavedMessagesRef.current = JSON.stringify(messagesWithDates);
      } else if (enableLocalStorageFallback) {
        // Try localStorage fallback
        console.log('[useConversationContext] Attempting localStorage fallback');
        const localKey = `conversation_${conversationId}`;
        const localData = localStorage.getItem(localKey);

        if (localData) {
          try {
            const parsed = JSON.parse(localData);
            const messagesWithDates: Message[] = parsed.messages?.map((msg: any) => ({
              ...msg,
              timestamp: new Date(msg.timestamp),
            })) || [];

            setMessages(messagesWithDates);
            console.log('[useConversationContext] Restored from localStorage');
          } catch (parseError) {
            console.error('[useConversationContext] Failed to parse localStorage data:', parseError);
          }
        }
      }
    } catch (error) {
      console.error('[useConversationContext] Failed to restore context:', error);
      setLoadingState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to restore context',
      }));
    } finally {
      setLoadingState(prev => ({ ...prev, isRestoring: false }));
      isRestoringRef.current = false;
    }
  }, [conversationId, enableLocalStorageFallback]);

  /**
   * Save conversation context to backend
   */
  const saveContext = useCallback(async () => {
    if (!conversationId || messages.length === 0) {
      return;
    }

    // Check if messages have changed
    const currentMessagesJson = JSON.stringify(messages);
    if (currentMessagesJson === lastSavedMessagesRef.current) {
      console.log('[useConversationContext] No changes to save');
      return;
    }

    setLoadingState(prev => ({ ...prev, isSaving: true, error: undefined }));

    try {
      console.log('[useConversationContext] Saving conversation context');

      const success = await contextApiHelpers.saveConversationSafely({
        user_id: userId,
        title: context?.conversation.title,
        messages,
        metadata: context?.conversation.metadata,
      });

      if (success) {
        lastSavedMessagesRef.current = currentMessagesJson;
        console.log('[useConversationContext] Context saved successfully');

        // Update localStorage as well
        if (enableLocalStorageFallback) {
          try {
            const localKey = `conversation_${conversationId}`;
            localStorage.setItem(localKey, JSON.stringify({ messages }));
          } catch (error) {
            console.warn('[useConversationContext] Failed to update localStorage:', error);
          }
        }
      } else {
        throw new Error('Failed to save conversation');
      }
    } catch (error) {
      console.error('[useConversationContext] Failed to save context:', error);
      setLoadingState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to save context',
      }));
    } finally {
      setLoadingState(prev => ({ ...prev, isSaving: false }));
    }
  }, [conversationId, userId, messages, context, enableLocalStorageFallback]);

  /**
   * Save search results to backend
   */
  const saveSearchResults = useCallback(
    async (results: GeoDatasetCandidate[], querySpec: any) => {
      if (!conversationId) {
        console.warn('[useConversationContext] Cannot save search: no conversation ID');
        return;
      }

      try {
        console.log('[useConversationContext] Saving search results:', results.length);

        await contextApi.saveSearch({
          conversation_id: conversationId,
          user_id: userId,
          query_spec: querySpec,
          results: results.map((r: any) => ({
            dataset_id: r.gse_id || r.studyId,
            rank: r.rank || 0,
            metadata: r,
          })),
        });

        setSearchResults(results);
        console.log('[useConversationContext] Search results saved');
      } catch (error) {
        console.error('[useConversationContext] Failed to save search results:', error);
        // Still update local state even if save fails
        setSearchResults(results);
      }
    },
    [conversationId, userId]
  );

  /**
   * Track dataset interaction
   */
  const trackDatasetInteraction = useCallback(
    async (
      datasetId: string,
      interactionType: 'view' | 'analyze' | 'download',
      metadata?: Record<string, any>
    ) => {
      if (!conversationId) {
        console.warn('[useConversationContext] Cannot track interaction: no conversation ID');
        return;
      }

      try {
        await contextApiHelpers.trackInteractionSafely({
          user_id: userId,
          dataset_id: datasetId,
          interaction_type: interactionType,
          conversation_id: conversationId,
          metadata,
        });

        console.log('[useConversationContext] Interaction tracked:', {
          datasetId,
          interactionType,
        });
      } catch (error) {
        console.error('[useConversationContext] Failed to track interaction:', error);
      }
    },
    [conversationId, userId]
  );

  /**
   * Clear context (for new conversation)
   */
  const clearContext = useCallback(() => {
    setMessages([]);
    setSearchResults(null);
    setContext(null);
    lastSavedMessagesRef.current = '';
  }, []);

  /**
   * Add a single message
   */
  const addMessage = useCallback((message: Message) => {
    setMessages(prev => [...prev, message]);
  }, []);

  /**
   * Auto-save when messages change
   */
  useEffect(() => {
    if (!autoSave || messages.length === 0 || !conversationId) {
      return;
    }

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Set new timeout for auto-save
    saveTimeoutRef.current = setTimeout(() => {
      saveContext();
    }, autoSaveDelay);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [messages, autoSave, autoSaveDelay, conversationId, saveContext]);

  /**
   * Restore context when conversation ID changes
   */
  useEffect(() => {
    if (conversationId) {
      restoreContext();
    } else {
      clearContext();
    }
  }, [conversationId, restoreContext, clearContext]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  return {
    messages,
    searchResults,
    loadingState,
    context,
    setMessages,
    addMessage,
    saveSearchResults,
    trackDatasetInteraction,
    restoreContext,
    saveContext,
    clearContext,
  };
}
