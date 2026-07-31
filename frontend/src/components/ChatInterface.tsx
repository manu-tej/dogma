import { useState, useRef, useEffect } from 'react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { ScrollArea } from './ui/scroll-area';
import { generateBioResponse, generateReasoningSteps, isGeoQuery } from '../utils/bioResponses';
import { searchGeoStreaming, parseNaturalLanguageQuery, type ProgressEvent } from '../services/geoSearchService';
import type { GeoDatasetCandidate, QuerySpec } from '@/lib/geo-client';
import { useConversationContext } from '../hooks/useConversationContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { useAutoPreferences } from '../hooks/useAutoPreferences';
import { LoadingOverlay, MessageSkeleton } from './LoadingSpinner';
import { DatasetHistoryPanel } from './DatasetHistoryPanel';
import { PreferenceSuggestion } from './PreferenceSuggestion';
import { ActivePreferencesBar } from './ActivePreferencesBar';
import { AlertCircle, History } from 'lucide-react';
import { Button } from './ui/button';
import type { PreferenceSuggestion as PreferenceSuggestionType } from '@/types/preferences';
import { getAnonUserId } from '@/lib/anonUser';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  reasoning?: ReasoningStep[];
  analysis?: {
    type: string;
    data: any;
  };
}

interface ReasoningStep {
  id: string;
  type: 'query_generation' | 'ncbi_search' | 'metadata_fetch' | 'filtering' | 'results';
  title: string;
  description: string;
  status: 'pending' | 'running' | 'complete';
  data?: any;  // Detailed step-specific data from SSE events
  progress?: number;  // Current progress count
  total?: number;  // Total items to process
}

interface ChatInterfaceProps {
  selectedDataset: string | null;
  conversationId: string | null;
  initialMessages: Message[];
  onUpdateMessages: (conversationId: string, messages: Message[]) => void;
  onOpenHypothesis?: (text: string) => void;
}

export function ChatInterface({ selectedDataset, conversationId, initialMessages, onUpdateMessages, onOpenHypothesis }: ChatInterfaceProps) {
  // Use context hook for persistence - SINGLE source of truth for messages
  const {
    messages,
    setMessages,
    searchResults,
    loadingState,
    saveSearchResults,
    trackDatasetInteraction,
    restoreContext,
  } = useConversationContext({
    conversationId,
    userId: getAnonUserId(),
    autoSave: true,
    autoSaveDelay: 500, // Reduced from 2000ms for faster saves
    enableLocalStorageFallback: true,
  });

  // Use preferences hook for managing user preferences
  const {
    preferences,
    suggestions,
    acceptSuggestion,
    rejectSuggestion,
    fetchSuggestions,
  } = useUserPreferences({
    userId: getAnonUserId(),
    autoFetch: true,
    fetchSuggestions: true,
    minSearchesForSuggestion: 5,
  });

  // Use auto-preferences hook for automatic preference application
  // Declared before useAutoPreferences below, which reads them (avoids a TDZ crash).
  const [preferencesEnabled, setPreferencesEnabled] = useState(true);
  const [skipPreferencesOnce, setSkipPreferencesOnce] = useState(false);

  const {
    applicablePreferences,
    applyPreferences,
    wouldModifyQuery,
    applicableCount,
  } = useAutoPreferences({
    preferences,
    isEnabled: preferencesEnabled && !skipPreferencesOnce,
    confidenceThreshold: 0.7,
  });

  const [isTyping, setIsTyping] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [showSuggestion, setShowSuggestion] = useState(false);
  const [currentSuggestion, setCurrentSuggestion] = useState<PreferenceSuggestionType | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousConversationId = useRef<string | null>(null);
  const previousQueryRef = useRef<string>(''); // Track last query for follow-up detection
  const [lastSearchResults, setLastSearchResults] = useState<GeoDatasetCandidate[] | null>(searchResults);
  const contextRestoredRef = useRef(false); // Track if context has been restored
  const searchCountRef = useRef(0); // Track number of searches for suggestion display

  // Sync search results when they change from context
  useEffect(() => {
    if (searchResults) {
      setLastSearchResults(searchResults);
    }
  }, [searchResults]);

  // Handle conversation changes and initial messages
  useEffect(() => {
    if (conversationId !== previousConversationId.current) {
      // Conversation switched
      previousConversationId.current = conversationId;
      contextRestoredRef.current = false; // Reset restoration flag

      // Load initial messages if this is a new conversation with no context
      if (messages.length === 0 && initialMessages.length > 0) {
        setMessages(initialMessages);
      }

      setIsTyping(false);
      setIsGenerating(false);
      previousQueryRef.current = ''; // Reset query tracking
      setLastSearchResults(null); // Reset search results for new conversation
    }
  }, [conversationId, initialMessages, messages.length, setMessages]);

  // Check for initial query from landing page (only after context is ready)
  useEffect(() => {
    const initialQuery = sessionStorage.getItem('initialQuery');

    // Only process if:
    // 1. We have an initial query
    // 2. Context is not currently loading
    // 3. We haven't processed this query yet (messages length check)
    if (initialQuery && !loadingState.isRestoring && !contextRestoredRef.current) {
      contextRestoredRef.current = true;
      sessionStorage.removeItem('initialQuery');

      // Small delay to ensure context is fully loaded
      setTimeout(() => {
        handleSendMessage(initialQuery);
      }, 100);
    }
  }, [conversationId, loadingState.isRestoring]);

  // Update parent whenever messages change
  useEffect(() => {
    if (conversationId && messages.length > 0) {
      onUpdateMessages(conversationId, messages);
    }
  }, [messages, conversationId, onUpdateMessages]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping, isGenerating]);

  // 1:1 mapping since frontend steps now match backend SSE events
  const stepMapping: Record<string, string> = {
    'query_generation': 'query_generation',
    'ncbi_search': 'ncbi_search',
    'metadata_fetch': 'metadata_fetch',
    'filtering': 'filtering',
    'results': 'results'
  };

  const handleSendMessage = async (content: string) => {
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date()
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);
    setIsGenerating(false);

    // Improved follow-up detection: Compare with previous query
    // A query is a follow-up if:
    // 1. We have previous search results
    // 2. The query references previous results OR is a meta-question
    const isFollowUpQuery = lastSearchResults &&
      previousQueryRef.current &&
      (
        // References to previous results
        /\b(these|those|them|it|this|that|above|previous)\b/i.test(content) ||
        // Questions about how to search/refine (meta-questions)
        /\b(differently|another way|try again|rephrase|else|other|more|less)\b/i.test(content) ||
        // Short conversational queries
        (content.length < 30 && !/\b(find|search|dataset|study|cancer|disease)\b/i.test(content))
      );

    // Check if this is a GEO query that should use real API
    // Must be a GEO query AND not a follow-up
    const shouldUseRealAPI = isGeoQuery(content) && !isFollowUpQuery;

    // If starting a new search, clear previous results
    if (shouldUseRealAPI) {
      setLastSearchResults(null);
      previousQueryRef.current = content; // Store current query for next comparison
      searchCountRef.current += 1; // Increment search count for suggestion trigger
    }

    // Create assistant message
    // Only show reasoning steps if we're actually performing a search (calling the tool)
    const assistantMessageId = (Date.now() + 1).toString();
    let geoResults: GeoDatasetCandidate[] | null = null;

    // If it's a GEO query, perform real API search with SSE progress
    if (shouldUseRealAPI) {
      // Parse the query into a QuerySpec
      let querySpec: QuerySpec = parseNaturalLanguageQuery(content);

      // Apply preferences if enabled and applicable
      if (preferencesEnabled && !skipPreferencesOnce && applicableCount > 0) {
        if (wouldModifyQuery(querySpec)) {
          console.log('[ChatInterface] Applying', applicableCount, 'preferences to query');
          querySpec = applyPreferences(querySpec);
        }
      }

      // Reset skip flag after use
      if (skipPreferencesOnce) {
        setSkipPreferencesOnce(false);
      }

      // Generate reasoning steps for actual searches
      const reasoningSteps = generateReasoningSteps(content);

      // Create assistant message with reasoning steps (initially all pending)
      const initialAssistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        reasoning: reasoningSteps.map(step => ({ ...step, status: 'pending' as const }))
      };

      setMessages((prev) => [...prev, initialAssistantMessage]);
      try {
        console.log('[ChatInterface] Starting SSE search for:', content);

        // Perform SSE search with real-time progress updates (use querySpec, not raw string)
        geoResults = await searchGeoStreaming(
          querySpec,
          (event: ProgressEvent) => {
            console.log('[ChatInterface] SSE Event:', event.step, event.status, event.message);

            // Map backend step to frontend reasoning step
            const frontendStepId = stepMapping[event.step] || event.step;

            // Update reasoning steps based on real progress
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id === assistantMessageId && msg.reasoning) {
                  const updatedReasoning = msg.reasoning.map(step => {
                    if (step.type === frontendStepId) {
                      // Update message if we have detailed progress
                      let updatedDescription = step.description;
                      if (event.progress && event.total) {
                        updatedDescription = `${event.message} (${event.progress}/${event.total})`;
                      } else if (event.message && event.status === 'running') {
                        updatedDescription = event.message;
                      }

                      return {
                        ...step,
                        status: event.status === 'error' ? 'complete' : event.status,
                        description: updatedDescription,
                        data: event.data,  // Store detailed step-specific data
                        progress: event.progress,  // Store current progress
                        total: event.total  // Store total count
                      };
                    }
                    return step;
                  });
                  return { ...msg, reasoning: updatedReasoning };
                }
                return msg;
              })
            );
          },
          conversationId || undefined
        );

        console.log('[ChatInterface] SSE search completed with', geoResults?.length || 0, 'results');

        // Store results for context-aware follow-ups
        setLastSearchResults(geoResults);

        // Persist search results to backend
        if (geoResults && geoResults.length > 0) {
          try {
            await saveSearchResults(geoResults, { query: content });
            console.log('[ChatInterface] Search results persisted to backend');
          } catch (error) {
            console.warn('[ChatInterface] Failed to persist search results:', error);
          }
        }

      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
        console.error('[ChatInterface] GEO search failed:', errorMessage);

        // Show clear error message to user
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id === assistantMessageId) {
              return {
                ...msg,
                content: `I encountered an error while searching: ${errorMessage}\n\nPlease try again or rephrase your query.`,
                reasoning: msg.reasoning?.map(step => ({ ...step, status: 'complete' as const }))
              };
            }
            return msg;
          })
        );

        // Don't continue with response generation on error
        setIsTyping(false);
        setIsGenerating(false);
        return;
      }
    } else {
      // Follow-up question or non-GEO query
      // Create simple assistant message without reasoning steps
      const initialAssistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        // No reasoning steps for follow-ups - just direct response
      };

      setMessages((prev) => [...prev, initialAssistantMessage]);

      // Use previous results if asking follow-up
      if (lastSearchResults) {
        geoResults = lastSearchResults;
      }
    }

    // After all steps complete, add the final response
    await new Promise(resolve => setTimeout(resolve, 500));

    const response = generateBioResponse(content, selectedDataset, geoResults);

    // Stop typing indicator and show generating indicator
    setIsTyping(false);
    setIsGenerating(true);

    await new Promise(resolve => setTimeout(resolve, 300));

    // Stream the response text
    const words = response.content.split(' ');
    let currentContent = '';

    setIsGenerating(false);

    for (let i = 0; i < words.length; i++) {
      currentContent += (i > 0 ? ' ' : '') + words[i];

      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id === assistantMessageId) {
            return {
              ...msg,
              content: currentContent,
              ...(i === words.length - 1 ? { analysis: response.analysis } : {})
            };
          }
          return msg;
        })
      );

      // Add a small delay between words for streaming effect
      await new Promise(resolve => setTimeout(resolve, 30));
    }
  };

  const handleAction = async (action: string, data?: any) => {
    switch (action) {
      case 'viewDetails':
        if (data && data.length > 0) {
          // Track interactions for each dataset
          for (const dataset of data) {
            const datasetId = dataset.studyId || dataset.gse_id;
            if (datasetId) {
              await trackDatasetInteraction(datasetId, 'view', { action: 'viewDetails' });
            }
          }
          const datasetIds = data.map((d: any) => d.studyId).join(', ');
          handleSendMessage(`Show me detailed information about datasets: ${datasetIds}`);
        }
        break;

      case 'analyzeMetadata':
        if (data && data.length > 0) {
          // Track analysis interactions
          for (const dataset of data) {
            const datasetId = dataset.studyId || dataset.gse_id;
            if (datasetId) {
              await trackDatasetInteraction(datasetId, 'analyze', { action: 'analyzeMetadata' });
            }
          }
          handleSendMessage('Analyze the metadata quality and completeness across these datasets');
        }
        break;

      case 'downloadSummary':
        if (data) {
          // Track download interactions
          if (data.datasetDetails) {
            for (const dataset of data.datasetDetails) {
              const datasetId = dataset.studyId || dataset.gse_id;
              if (datasetId) {
                await trackDatasetInteraction(datasetId, 'download', { action: 'downloadSummary' });
              }
            }
          }
          // Create CSV content
          const csvContent = generateCSVSummary(data);
          // Trigger download
          const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
          const link = document.createElement('a');
          const url = URL.createObjectURL(blob);
          link.setAttribute('href', url);
          link.setAttribute('download', `dataset_summary_${Date.now()}.csv`);
          link.style.visibility = 'hidden';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
        break;

      case 'runSurvivalAnalysis':
        if (data && data.length > 0) {
          // Track analysis interactions
          for (const dataset of data) {
            const datasetId = dataset.studyId || dataset.gse_id;
            if (datasetId) {
              await trackDatasetInteraction(datasetId, 'analyze', { action: 'runSurvivalAnalysis' });
            }
          }
          const datasetIds = data.map((d: any) => d.studyId).join(', ');
          handleSendMessage(`Run survival analysis on datasets with survival data: ${datasetIds}`);
        } else {
          handleSendMessage('No datasets with survival data available for analysis');
        }
        break;

      case 'suggestedReply':
        if (data) {
          handleSendMessage(data);
        }
        break;
    }
  };

  const generateCSVSummary = (data: any) => {
    if (!data.datasetDetails) return '';

    const headers = ['Study ID', 'Organism', 'Tissue/Cell Type', 'Sample Count', 'Platform', 'Survival Data'];
    const rows = data.datasetDetails.map((dataset: any) => [
      dataset.studyId,
      dataset.organism,
      dataset.tissue,
      dataset.sampleCount,
      dataset.platform,
      // Hedged in the export too: a CSV outlives the UI that explained it.
      dataset.maybeHasSurvivalData ? 'likely (inferred)' : 'not indicated'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row: string[]) => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    return csvContent;
  };

  const handleDatasetSelect = (datasetId: string, metadata?: Record<string, any>) => {
    // When a dataset is selected from history, load it into the conversation
    const message = metadata?.title
      ? `Tell me more about ${datasetId}: ${metadata.title}`
      : `Show me details about dataset ${datasetId}`;

    handleSendMessage(message);
  };

  const handleApplyPreferences = () => {
    // Build a search query incorporating user preferences
    const preferenceMessages: string[] = [];

    preferences.forEach(pref => {
      if (pref.preferenceValue?.preferred && Array.isArray(pref.preferenceValue.preferred)) {
        const values = pref.preferenceValue.preferred.join(', ');
        preferenceMessages.push(`${pref.preferenceType}: ${values}`);
      }
    });

    if (preferenceMessages.length > 0) {
      const query = `Search for datasets matching my preferences: ${preferenceMessages.join('; ')}`;
      handleSendMessage(query);
    }
  };

  const handleAcceptSuggestion = async (suggestion: PreferenceSuggestionType) => {
    const result = await acceptSuggestion(suggestion);
    if (result) {
      setShowSuggestion(false);
      setCurrentSuggestion(null);
      console.log('[ChatInterface] Suggestion accepted and saved as preference');
    }
  };

  const handleRejectSuggestion = (suggestion: PreferenceSuggestionType) => {
    rejectSuggestion(suggestion);
    setShowSuggestion(false);
    setCurrentSuggestion(null);
    console.log('[ChatInterface] Suggestion rejected');
  };

  // Check for suggestions after searches
  useEffect(() => {
    if (searchCountRef.current >= 5 && suggestions.length > 0 && !showSuggestion) {
      // Show first suggestion after 5 searches
      setCurrentSuggestion(suggestions[0]);
      setShowSuggestion(true);
      searchCountRef.current = 0; // Reset counter
    }
  }, [searchCountRef.current, suggestions, showSuggestion]);

  return (
    <div className="flex-1 flex bg-background">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Loading overlay during context restoration */}
        {loadingState.isRestoring && <LoadingOverlay text="Restoring conversation..." />}

        {/* Error banner */}
        {loadingState.error && (
          <div className="bg-destructive/15 border-b border-destructive/40 px-6 py-3">
            <div className="max-w-4xl mx-auto flex items-center gap-2 text-destructive">
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm">{loadingState.error}</span>
            </div>
          </div>
        )}

        {/* Messages Area */}
        <ScrollArea className="flex-1 p-6 bg-background">
          <div ref={scrollRef} className="max-w-4xl mx-auto space-y-6">
            {loadingState.isRestoring ? (
              <MessageSkeleton />
            ) : (
              <>
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} onAction={handleAction} />
                ))}

                {/* Preference Suggestion (after pattern detection) */}
                {showSuggestion && currentSuggestion && (
                  <PreferenceSuggestion
                    suggestion={currentSuggestion}
                    onAccept={handleAcceptSuggestion}
                    onReject={handleRejectSuggestion}
                  />
                )}
              </>
            )}
            {isGenerating && (
              <div className="flex gap-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
                <div className="w-8 h-8 rounded-full bg-signal flex items-center justify-center text-primary-foreground text-xs font-mono animate-pulse">
                  AI
                </div>
                <div className="bg-card rounded-xl p-4 border border-border elev">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-signal rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-signal rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-signal rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="border-t border-border bg-surface-1/80 backdrop-blur-xl p-6">
          <div className="max-w-4xl mx-auto space-y-3">
            {/* Active Preferences Bar */}
            {applicablePreferences.length > 0 && (
              <div className="space-y-2">
                <ActivePreferencesBar
                  preferences={applicablePreferences}
                  isEnabled={preferencesEnabled}
                  onToggle={setPreferencesEnabled}
                />
                {preferencesEnabled && applicableCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSkipPreferencesOnce(true)}
                    className="text-xs text-muted-foreground hover:text-foreground/90 hover:bg-accent"
                  >
                    Skip preferences for next search
                  </Button>
                )}
              </div>
            )}

            <div className="flex items-end gap-2">
              <div className="flex-1">
                <ChatInput
                  onSendMessage={handleSendMessage}
                  disabled={isTyping}
                  hasPreferences={preferences.length > 0}
                  onApplyPreferences={handleApplyPreferences}
                  preferencesActive={preferencesEnabled && !skipPreferencesOnce}
                  applicableCount={applicableCount}
                  onOpenHypothesis={onOpenHypothesis}
                />
                {selectedDataset && (
                  <p className="text-muted-foreground text-sm mt-2 animate-in fade-in duration-300">
                    Querying: <span className="text-signal font-mono">{selectedDataset.toUpperCase()}</span> dataset
                  </p>
                )}
              </div>

              {/* History Toggle Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsHistoryOpen(!isHistoryOpen)}
                className={`border-border hover:bg-accent hover:border-border-strong transition-colors ${
                  isHistoryOpen ? 'bg-accent border-signal/50 text-signal' : 'text-muted-foreground'
                }`}
                title="Dataset History"
              >
                <History className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Dataset History Panel */}
      <DatasetHistoryPanel
        userId={getAnonUserId()}
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onDatasetSelect={handleDatasetSelect}
      />
    </div>
  );
}
