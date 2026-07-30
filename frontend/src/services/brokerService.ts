/**
 * Service for interacting with the Method Broker API
 */

import { API_BASE_URL } from "@/lib/apiBaseUrl";

export interface MethodRequest {
  query: string;
  data_modality?: string;
  sample_metadata?: Record<string, any>;
  execute?: boolean;
  max_recommendations?: number;
  prefer_published?: boolean;
  prefer_reproducible?: boolean;
  min_quality_score?: number;
  conversation_id?: string;
  user_id?: string;
}

export interface MethodInputSpec {
  name: string;
  description: string;
  data_type: string;
  required: boolean;
  multiple: boolean;
  example?: string;
}

export interface MethodOutputSpec {
  name: string;
  description: string;
  data_type: string;
  file_pattern?: string;
}

export interface MethodAssumption {
  description: string;
  category: string;
  critical: boolean;
}

export interface MethodCaveat {
  description: string;
  severity: string;
  workaround?: string;
}

export interface MethodQualityMetrics {
  reproducibility_score: number;
  code_availability: boolean;
  documentation_quality: number;
  peer_reviewed: boolean;
  citation_count: number;
  last_updated?: string;
  community_rating?: number;
}

export interface AnalysisMethod {
  id: string;
  name: string;
  category: string;
  description: string;
  implementation_type: string;
  version: string;
  repository_url?: string;
  documentation_url?: string;
  inputs: MethodInputSpec[];
  outputs: MethodOutputSpec[];
  supported_modalities: string[];
  supported_organisms?: string[];
  min_samples?: number;
  max_samples?: number;
  assumptions: MethodAssumption[];
  caveats: MethodCaveat[];
  quality_metrics: MethodQualityMetrics;
  compute_requirements: Record<string, any>;
  estimated_runtime?: string;
  created_at: string;
  created_by: string;
  tags: string[];
  status: string;
  publications: string[];
}

export interface ParsedRequest {
  original_query: string;
  data_modality: string;
  analysis_type: string;
  specific_tools: string[];
  organism?: string;
  sample_count?: number;
  experimental_design?: string;
  constraints: Record<string, any>;
  preferences: Record<string, any>;
  keywords: string[];
  confidence: number;
  parsed_at: string;
}

export interface MatchResult {
  method: AnalysisMethod;
  score: number;
  relevance_score: number;
  quality_score: number;
  compatibility_score: number;
  match_reasons: string[];
  potential_issues: string[];
  recommended: boolean;
  rank: number;
}

export interface MethodResponse {
  request: MethodRequest;
  parsed_request: ParsedRequest;
  matches: MatchResult[];
  execution_result?: Record<string, any>;
  processing_time_ms: number;
  timestamp: string;
}

export interface MethodProposal {
  name: string;
  category: string;
  description: string;
  justification: string;
  use_cases: string[];
  repository_url?: string;
  documentation_url?: string;
  publications?: string[];
  advantages_over_existing?: string;
  proposed_by: string;
  proposed_at?: string;
  status?: string;
  review_notes?: string;
}

export interface RegistryStats {
  registry: {
    total_methods: number;
    by_category: Record<string, number>;
    by_status: Record<string, number>;
    average_quality_score: number;
  };
  proposals: {
    total_proposals: number;
    by_status: Record<string, number>;
    recent_proposals: number;
  };
}

/**
 * Match user request to appropriate analysis methods
 */
export async function matchMethods(
  request: MethodRequest
): Promise<MethodResponse> {
  const response = await fetch(`${API_BASE_URL}/broker/match`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to match methods: ${response.statusText}`);
  }

  return response.json();
}

/**
 * List all available methods
 */
export async function listMethods(params?: {
  category?: string;
  modality?: string;
  search?: string;
}): Promise<AnalysisMethod[]> {
  const queryParams = new URLSearchParams();
  if (params?.category) queryParams.append("category", params.category);
  if (params?.modality) queryParams.append("modality", params.modality);
  if (params?.search) queryParams.append("search", params.search);

  const url = `${API_BASE_URL}/broker/methods${
    queryParams.toString() ? `?${queryParams.toString()}` : ""
  }`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to list methods: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a specific method by ID
 */
export async function getMethod(methodId: string): Promise<AnalysisMethod> {
  const response = await fetch(`${API_BASE_URL}/broker/methods/${methodId}`);

  if (!response.ok) {
    throw new Error(`Failed to get method: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get broker and registry statistics
 */
export async function getStats(): Promise<RegistryStats> {
  const response = await fetch(`${API_BASE_URL}/broker/stats`);

  if (!response.ok) {
    throw new Error(`Failed to get stats: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Submit a method proposal
 */
export async function submitProposal(
  proposal: MethodProposal
): Promise<{ proposal_id: string; status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/broker/proposals`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(proposal),
  });

  if (!response.ok) {
    throw new Error(`Failed to submit proposal: ${response.statusText}`);
  }

  return response.json();
}

/**
 * List method proposals
 */
export async function listProposals(params?: {
  status?: string;
  proposed_by?: string;
}): Promise<MethodProposal[]> {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append("status", params.status);
  if (params?.proposed_by) queryParams.append("proposed_by", params.proposed_by);

  const url = `${API_BASE_URL}/broker/proposals${
    queryParams.toString() ? `?${queryParams.toString()}` : ""
  }`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to list proposals: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a specific proposal
 */
export async function getProposal(
  proposalId: string
): Promise<MethodProposal> {
  const response = await fetch(
    `${API_BASE_URL}/broker/proposals/${proposalId}`
  );

  if (!response.ok) {
    throw new Error(`Failed to get proposal: ${response.statusText}`);
  }

  return response.json();
}
