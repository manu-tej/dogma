/**
 * Type definitions for Context API
 *
 * These types match the backend models and API responses for conversation context,
 * searches, interactions, and dataset history.
 */

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  reasoning?: ReasoningStep[];
  analysis?: {
    type: string;
    data: any;
  };
  metadata?: Record<string, any>;
}

export interface ReasoningStep {
  id: string;
  type: 'query_generation' | 'ncbi_search' | 'metadata_fetch' | 'filtering' | 'results';
  title: string;
  description: string;
  status: 'pending' | 'running' | 'complete';
  data?: any;
  progress?: number;
  total?: number;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_archived?: boolean;
  project_id?: string;
  metadata?: Record<string, any>;
}

export interface Search {
  id: string;
  conversation_id: string;
  query_spec: Record<string, any>;
  result_count: number;
  execution_time_ms?: number;
  created_at: string;
  results?: SearchResult[];
}

export interface SearchResult {
  dataset_id: string;
  rank: number;
  metadata: Record<string, any>;
}

export interface UserInteraction {
  id: string;
  dataset_id: string;
  interaction_type: 'view' | 'analyze' | 'download';
  created_at: string;
  conversation_id?: string;
  search_id?: string;
  metadata?: Record<string, any>;
}

export interface ConversationContext {
  conversation: Conversation;
  messages: Message[];
  searches: Search[];
  interactions: UserInteraction[];
}

export interface DatasetHistory {
  dataset_id: string;
  has_viewed: boolean;
  first_viewed_at?: string;
  interaction_count: number;
  interactions: Array<{
    type: string;
    created_at: string;
    conversation_id?: string;
  }>;
  related_searches: Array<{
    id: string;
    conversation_id: string;
    created_at: string;
  }>;
}

export interface UserContextSummary {
  user_id: string;
  statistics: {
    total_conversations: number;
    total_searches: number;
    total_interactions: number;
    unique_datasets_viewed: number;
    saved_preferences: number;
  };
  recent_conversations: Array<{
    id: string;
    title: string;
    updated_at: string;
  }>;
  interaction_breakdown: {
    views: number;
    analyses: number;
    downloads: number;
  };
}

export interface RecalledDataset {
  dataset_id: string;
  dataset_type: string;
  last_interaction: string;
  interaction_types: Array<'view' | 'analyze' | 'download'>;
  interaction_count: number;
  first_seen: string;
  metadata?: Record<string, any>;
}

// API Request/Response types
export interface SaveConversationRequest {
  user_id: string;
  title?: string;
  messages: Message[];
  metadata?: Record<string, any>;
}

export interface SaveSearchRequest {
  conversation_id: string;
  user_id: string;
  query_spec: Record<string, any>;
  results: any[];
  execution_time_ms?: number;
}

export interface TrackInteractionRequest {
  user_id: string;
  dataset_id: string;
  interaction_type: 'view' | 'analyze' | 'download';
  conversation_id?: string;
  search_id?: string;
  metadata?: Record<string, any>;
}

// Loading states
export interface ContextLoadingState {
  isLoading: boolean;
  isRestoring: boolean;
  isSaving: boolean;
  error?: string;
}
