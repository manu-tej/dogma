"""Pydantic schemas for API request/response models."""

from quration.api.schemas.context import (
    ConversationContextResponse,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationStateResponse,
    MessageCreateRequest,
    MessageResponse,
)
from quration.api.schemas.interaction import (
    InteractionHistoryResponse,
    InteractionRecordRequest,
    InteractionResponse,
    InteractionStatsResponse,
)
from quration.api.schemas.preferences import (
    PreferenceCreateRequest,
    PreferenceResponse,
    PreferenceUpdateRequest,
    UserPreferencesResponse,
)
from quration.api.schemas.search import (
    SearchCreateRequest,
    SearchResponse,
    SearchResultResponse,
    SearchWithResultsResponse,
)
from quration.api.schemas.interpretation import (
    # Request schemas
    InterpretDEGRequest,
    InterpretPathwayRequest,
    AnalyzeGeneFunctionRequest,
    AssessBatchEffectsRequest,
    ReviewLiteratureRequest,
    CustomInterpretationRequest,
    # Response schemas
    InterpretDEGResponse,
    InterpretPathwayResponse,
    AnalyzeGeneFunctionResponse,
    AssessBatchEffectsResponse,
    ReviewLiteratureResponse,
    CustomInterpretationResponse,
    # Shared schemas
    GeneExpressionItem,
    PathwayEnrichmentItem,
    ToolCallSummary,
    ClaimResponse,
    TokenUsageResponse,
    InterpretationStatusResponse,
    InterpretationErrorResponse,
    AvailableToolsResponse,
    InterpretationMetricsResponse,
)

__all__ = [
    # Context schemas
    "ConversationContextResponse",
    "ConversationCreateRequest",
    "ConversationResponse",
    "ConversationStateResponse",
    "MessageCreateRequest",
    "MessageResponse",
    # Interaction schemas
    "InteractionHistoryResponse",
    "InteractionRecordRequest",
    "InteractionResponse",
    "InteractionStatsResponse",
    # Preference schemas
    "PreferenceCreateRequest",
    "PreferenceResponse",
    "PreferenceUpdateRequest",
    "UserPreferencesResponse",
    # Search schemas
    "SearchCreateRequest",
    "SearchResponse",
    "SearchResultResponse",
    "SearchWithResultsResponse",
    # Interpretation schemas
    "InterpretDEGRequest",
    "InterpretPathwayRequest",
    "AnalyzeGeneFunctionRequest",
    "AssessBatchEffectsRequest",
    "ReviewLiteratureRequest",
    "CustomInterpretationRequest",
    "InterpretDEGResponse",
    "InterpretPathwayResponse",
    "AnalyzeGeneFunctionResponse",
    "AssessBatchEffectsResponse",
    "ReviewLiteratureResponse",
    "CustomInterpretationResponse",
    "GeneExpressionItem",
    "PathwayEnrichmentItem",
    "ToolCallSummary",
    "ClaimResponse",
    "TokenUsageResponse",
    "InterpretationStatusResponse",
    "InterpretationErrorResponse",
    "AvailableToolsResponse",
    "InterpretationMetricsResponse",
]
