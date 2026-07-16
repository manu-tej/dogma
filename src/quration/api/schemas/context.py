"""Pydantic schemas for context management endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "role": "user",
                "content": "Find melanoma immunotherapy datasets",
                "createdAt": "2024-01-01T12:00:00Z",
                "metadata": {}
            }
        }


class MessageCreateRequest(BaseModel):
    """Request model for creating a message."""

    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content", min_length=1)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "Find melanoma immunotherapy datasets",
                "metadata": {}
            }
        }


class ConversationResponse(BaseModel):
    """Response model for a conversation."""

    id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., alias="userId", description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")
    tags: Optional[List[str]] = Field(None, description="Conversation tags")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    updated_at: str = Field(..., alias="updatedAt", description="ISO timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "userId": "user-123",
                "title": "Melanoma Research",
                "tags": ["melanoma", "rna-seq"],
                "createdAt": "2024-01-01T12:00:00Z",
                "updatedAt": "2024-01-01T12:00:00Z",
                "metadata": {}
            }
        }


class ConversationCreateRequest(BaseModel):
    """Request model for creating a conversation."""

    title: Optional[str] = Field(None, description="Conversation title", max_length=500)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Melanoma Research",
                "metadata": {"tags": ["research", "melanoma"]}
            }
        }


class SearchSummaryResponse(BaseModel):
    """Summary of a search within context."""

    id: str = Field(..., description="Search ID")
    query_spec: Dict[str, Any] = Field(..., alias="querySpec", description="Query specification")
    result_count: Optional[int] = Field(None, alias="resultCount", description="Number of results")
    execution_time_ms: Optional[int] = Field(None, alias="executionTimeMs", description="Execution time in ms")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")

    class Config:
        populate_by_name = True


class InteractionSummaryResponse(BaseModel):
    """Summary of an interaction within context."""

    id: str = Field(..., description="Interaction ID")
    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    interaction_type: str = Field(..., alias="interactionType", description="Interaction type")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        populate_by_name = True


class UserStatisticsResponse(BaseModel):
    """User activity statistics."""

    total_conversations: int = Field(..., alias="totalConversations")
    total_searches: int = Field(..., alias="totalSearches")
    total_interactions: int = Field(..., alias="totalInteractions")
    unique_datasets_viewed: int = Field(..., alias="uniqueDatasetsViewed")
    saved_preferences: int = Field(..., alias="savedPreferences")

    class Config:
        populate_by_name = True


class RecentConversationSummary(BaseModel):
    """Recent conversation summary."""

    id: str
    title: str
    updated_at: str = Field(..., alias="updatedAt")

    class Config:
        populate_by_name = True


class InteractionBreakdown(BaseModel):
    """Breakdown of interactions by type."""

    views: int
    analyses: int
    downloads: int


class UserContextSummaryResponse(BaseModel):
    """User context summary with statistics and recent activity."""

    user_id: str = Field(..., alias="userId")
    statistics: UserStatisticsResponse
    recent_conversations: List[RecentConversationSummary] = Field(..., alias="recentConversations")
    interaction_breakdown: InteractionBreakdown = Field(..., alias="interactionBreakdown")

    class Config:
        populate_by_name = True


class ConversationContextResponse(BaseModel):
    """Response model for full conversation context."""

    conversation: ConversationResponse = Field(..., description="Conversation details")
    messages: List[MessageResponse] = Field(..., description="List of messages")
    searches: List[SearchSummaryResponse] = Field(..., description="List of searches")
    interactions: List[InteractionSummaryResponse] = Field(..., description="List of interactions")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "userId": "user-123",
                    "title": "Melanoma Research",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "updatedAt": "2024-01-01T12:00:00Z",
                    "metadata": {}
                },
                "messages": [
                    {
                        "id": "msg-1",
                        "role": "user",
                        "content": "Find melanoma datasets",
                        "createdAt": "2024-01-01T12:00:00Z"
                    }
                ],
                "searches": [],
                "interactions": []
            }
        }


class SearchResultSummary(BaseModel):
    """Summary of search result within conversation state."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    rank: Optional[int] = Field(None, description="Result rank")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Dataset metadata")

    class Config:
        populate_by_name = True


class SearchWithResultsSummary(BaseModel):
    """Search with results for conversation state."""

    id: str = Field(..., description="Search ID")
    query_spec: Dict[str, Any] = Field(..., alias="querySpec", description="Query specification")
    result_count: Optional[int] = Field(None, alias="resultCount", description="Number of results")
    execution_time_ms: Optional[int] = Field(None, alias="executionTimeMs", description="Execution time in ms")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    results: List[SearchResultSummary] = Field(..., description="Search results")

    class Config:
        populate_by_name = True


class ConversationStateResponse(BaseModel):
    """Response model for complete conversation state restoration."""

    conversation: ConversationResponse = Field(..., description="Conversation details")
    messages: List[MessageResponse] = Field(..., description="List of messages")
    searches: List[SearchWithResultsSummary] = Field(..., description="List of searches with results")
    interactions: List[InteractionSummaryResponse] = Field(..., description="List of interactions")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "userId": "user-123",
                    "title": "Melanoma Research",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "updatedAt": "2024-01-01T12:00:00Z"
                },
                "messages": [],
                "searches": [
                    {
                        "id": "search-1",
                        "querySpec": {"diseaseTerms": ["melanoma"]},
                        "resultCount": 10,
                        "executionTimeMs": 1500,
                        "createdAt": "2024-01-01T12:00:00Z",
                        "results": [
                            {
                                "datasetId": "GSE123456",
                                "rank": 1,
                                "metadata": {"title": "Melanoma study"}
                            }
                        ]
                    }
                ],
                "interactions": []
            }
        }


class AddTagsRequest(BaseModel):
    """Request model for adding tags to a conversation."""

    tags: List[str] = Field(
        ...,
        description="List of tags to add",
        min_length=1,
        max_length=20
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tags": ["experiment", "rna-seq", "melanoma"]
            }
        }


class ConversationSearchResponse(BaseModel):
    """Response model for conversation search results."""

    id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., alias="userId", description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")
    tags: List[str] = Field(default_factory=list, description="Conversation tags")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    updated_at: str = Field(..., alias="updatedAt", description="ISO timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    relevance_score: float = Field(..., alias="relevanceScore", description="Search relevance score")
    message_count: int = Field(..., alias="messageCount", description="Number of messages")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "userId": "user-123",
                "title": "Melanoma RNA-Seq Analysis",
                "tags": ["melanoma", "rna-seq"],
                "createdAt": "2024-01-01T12:00:00Z",
                "updatedAt": "2024-01-01T15:30:00Z",
                "metadata": {},
                "relevanceScore": 1.7,
                "messageCount": 12
            }
        }
