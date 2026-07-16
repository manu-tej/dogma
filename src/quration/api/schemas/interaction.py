"""Pydantic schemas for interaction tracking endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InteractionResponse(BaseModel):
    """Response model for a user interaction."""

    id: str = Field(..., description="Interaction ID")
    user_id: str = Field(..., alias="userId", description="User ID")
    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID (e.g., GSE123456)")
    interaction_type: str = Field(..., alias="interactionType", description="Type (view, analyze, download)")
    conversation_id: Optional[str] = Field(None, alias="conversationId", description="Optional conversation ID")
    search_id: Optional[str] = Field(None, alias="searchId", description="Optional search ID")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "interaction-123",
                "userId": "user-123",
                "datasetId": "GSE123456",
                "interactionType": "view",
                "conversationId": "conv-123",
                "searchId": "search-123",
                "createdAt": "2024-01-01T12:00:00Z",
                "metadata": {"duration_seconds": 45}
            }
        }


class InteractionRecordRequest(BaseModel):
    """Request model for recording an interaction."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID", min_length=1)
    interaction_type: str = Field(
        ...,
        alias="interactionType",
        description="Interaction type (view, analyze, download)",
        pattern="^(view|analyze|download)$"
    )
    conversation_id: Optional[str] = Field(None, alias="conversationId", description="Optional conversation ID")
    search_id: Optional[str] = Field(None, alias="searchId", description="Optional search ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "datasetId": "GSE123456",
                "interactionType": "view",
                "conversationId": "conv-123",
                "searchId": "search-123",
                "metadata": {"source": "search_results", "position": 1}
            }
        }


class InteractionHistoryResponse(BaseModel):
    """Response model for interaction history."""

    interactions: List[InteractionResponse] = Field(..., description="List of interactions")
    total: int = Field(..., description="Total number of interactions")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")

    class Config:
        json_schema_extra = {
            "example": {
                "interactions": [
                    {
                        "id": "interaction-123",
                        "userId": "user-123",
                        "datasetId": "GSE123456",
                        "interactionType": "view",
                        "createdAt": "2024-01-01T12:00:00Z"
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0
            }
        }


class InteractionStatsResponse(BaseModel):
    """Response model for interaction statistics."""

    total_interactions: int = Field(..., alias="totalInteractions", description="Total number of interactions")
    view_count: int = Field(..., alias="viewCount", description="Number of view interactions")
    analyze_count: int = Field(..., alias="analyzeCount", description="Number of analyze interactions")
    download_count: int = Field(..., alias="downloadCount", description="Number of download interactions")
    unique_datasets: int = Field(..., alias="uniqueDatasets", description="Number of unique datasets interacted with")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "totalInteractions": 150,
                "viewCount": 100,
                "analyzeCount": 30,
                "downloadCount": 20,
                "uniqueDatasets": 45
            }
        }


class DatasetInteractionHistoryResponse(BaseModel):
    """Response model for dataset-specific interaction history."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    has_viewed: bool = Field(..., alias="hasViewed", description="Whether user has viewed this dataset")
    first_viewed_at: Optional[str] = Field(None, alias="firstViewedAt", description="First view timestamp")
    interaction_count: int = Field(..., alias="interactionCount", description="Total interactions with this dataset")
    interactions: List[InteractionResponse] = Field(..., description="List of interactions")
    related_searches: List[Dict[str, Any]] = Field(..., alias="relatedSearches", description="Related searches")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "datasetId": "GSE123456",
                "hasViewed": True,
                "firstViewedAt": "2024-01-01T12:00:00Z",
                "interactionCount": 3,
                "interactions": [
                    {
                        "id": "interaction-123",
                        "userId": "user-123",
                        "datasetId": "GSE123456",
                        "interactionType": "view",
                        "createdAt": "2024-01-01T12:00:00Z"
                    }
                ],
                "relatedSearches": [
                    {
                        "id": "search-123",
                        "conversationId": "conv-123",
                        "createdAt": "2024-01-01T12:00:00Z"
                    }
                ]
            }
        }


class RecalledDatasetItem(BaseModel):
    """Response model for a recalled dataset item."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    last_interaction_at: str = Field(..., alias="lastInteractionAt", description="Most recent interaction timestamp")
    interaction_count: int = Field(..., alias="interactionCount", description="Total interactions with this dataset")
    last_interaction_type: str = Field(..., alias="lastInteractionType", description="Type of most recent interaction")
    conversation_id: Optional[str] = Field(None, alias="conversationId", description="ID of conversation with last interaction")
    conversation_title: Optional[str] = Field(None, alias="conversationTitle", description="Title of conversation with last interaction")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "datasetId": "GSE123456",
                "lastInteractionAt": "2024-01-01T12:00:00Z",
                "interactionCount": 5,
                "lastInteractionType": "view",
                "conversationId": "conv-123",
                "conversationTitle": "Cancer gene expression analysis"
            }
        }


class RecalledDatasetsResponse(BaseModel):
    """Response model for recalled datasets across conversations."""

    datasets: List[RecalledDatasetItem] = Field(..., description="List of recalled datasets")
    total: int = Field(..., description="Total number of datasets")
    limit: int = Field(..., description="Limit used for pagination")

    class Config:
        json_schema_extra = {
            "example": {
                "datasets": [
                    {
                        "datasetId": "GSE123456",
                        "lastInteractionAt": "2024-01-01T12:00:00Z",
                        "interactionCount": 5,
                        "lastInteractionType": "view",
                        "conversationId": "conv-123",
                        "conversationTitle": "Cancer gene expression"
                    }
                ],
                "total": 1,
                "limit": 10
            }
        }


class DatasetConversationItem(BaseModel):
    """Response model for a conversation containing a dataset."""

    conversation_id: str = Field(..., alias="conversationId", description="Conversation ID")
    conversation_title: Optional[str] = Field(None, alias="conversationTitle", description="Conversation title")
    first_interaction_at: str = Field(..., alias="firstInteractionAt", description="First interaction with dataset in this conversation")
    interaction_count: int = Field(..., alias="interactionCount", description="Number of interactions in this conversation")
    interaction_types: List[str] = Field(..., alias="interactionTypes", description="Types of interactions in this conversation")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "conversationId": "conv-123",
                "conversationTitle": "Cancer gene expression analysis",
                "firstInteractionAt": "2024-01-01T12:00:00Z",
                "interactionCount": 3,
                "interactionTypes": ["view", "analyze"]
            }
        }


class DatasetConversationsResponse(BaseModel):
    """Response model for conversations containing a dataset."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    conversations: List[DatasetConversationItem] = Field(..., description="List of conversations")
    total_conversations: int = Field(..., alias="totalConversations", description="Total number of conversations")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "datasetId": "GSE123456",
                "conversations": [
                    {
                        "conversationId": "conv-123",
                        "conversationTitle": "Cancer gene expression",
                        "firstInteractionAt": "2024-01-01T12:00:00Z",
                        "interactionCount": 3,
                        "interactionTypes": ["view", "analyze"]
                    }
                ],
                "totalConversations": 1
            }
        }
