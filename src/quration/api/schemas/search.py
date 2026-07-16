"""Pydantic schemas for search management endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchResultResponse(BaseModel):
    """Response model for a search result."""

    id: str = Field(..., description="Result ID")
    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID (e.g., GSE123456)")
    rank: Optional[int] = Field(None, description="Result rank in search")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Dataset metadata")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "result-123",
                "datasetId": "GSE123456",
                "rank": 1,
                "metadata": {
                    "title": "Melanoma immunotherapy study",
                    "organism": "Homo sapiens"
                },
                "createdAt": "2024-01-01T12:00:00Z"
            }
        }


class SearchResponse(BaseModel):
    """Response model for a search query."""

    id: str = Field(..., description="Search ID")
    conversation_id: str = Field(..., alias="conversationId", description="Conversation ID")
    user_id: str = Field(..., alias="userId", description="User ID")
    query_spec: Dict[str, Any] = Field(..., alias="querySpec", description="Complete query specification")
    result_count: Optional[int] = Field(None, alias="resultCount", description="Number of results")
    execution_time_ms: Optional[int] = Field(None, alias="executionTimeMs", description="Execution time in milliseconds")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "search-123",
                "conversationId": "conv-123",
                "userId": "user-123",
                "querySpec": {
                    "diseaseTerms": ["melanoma"],
                    "therapyClass": "immunotherapy",
                    "therapyScope": "specific"
                },
                "resultCount": 10,
                "executionTimeMs": 1500,
                "createdAt": "2024-01-01T12:00:00Z"
            }
        }


class SearchWithResultsResponse(BaseModel):
    """Response model for a search with its results."""

    search: SearchResponse = Field(..., description="Search details")
    results: List[SearchResultResponse] = Field(..., description="Search results")

    class Config:
        json_schema_extra = {
            "example": {
                "search": {
                    "id": "search-123",
                    "conversationId": "conv-123",
                    "userId": "user-123",
                    "querySpec": {"diseaseTerms": ["melanoma"]},
                    "resultCount": 1,
                    "executionTimeMs": 1500,
                    "createdAt": "2024-01-01T12:00:00Z"
                },
                "results": [
                    {
                        "id": "result-123",
                        "datasetId": "GSE123456",
                        "rank": 1,
                        "metadata": {"title": "Melanoma study"},
                        "createdAt": "2024-01-01T12:00:00Z"
                    }
                ]
            }
        }


class SearchResultCreateRequest(BaseModel):
    """Request model for creating a search result."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    rank: Optional[int] = Field(None, description="Result rank")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Dataset metadata")

    class Config:
        populate_by_name = True


class SearchCreateRequest(BaseModel):
    """Request model for creating a search."""

    conversation_id: str = Field(..., alias="conversationId", description="Conversation ID")
    query_spec: Dict[str, Any] = Field(..., alias="querySpec", description="Complete query specification")
    execution_time_ms: Optional[int] = Field(None, alias="executionTimeMs", description="Execution time in ms")
    results: List[SearchResultCreateRequest] = Field(default_factory=list, description="Search results")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "conversationId": "conv-123",
                "querySpec": {
                    "diseaseTerms": ["melanoma"],
                    "therapyClass": "immunotherapy",
                    "therapyScope": "specific"
                },
                "executionTimeMs": 1500,
                "results": [
                    {
                        "datasetId": "GSE123456",
                        "rank": 1,
                        "metadata": {
                            "title": "Melanoma immunotherapy study",
                            "organism": "Homo sapiens"
                        }
                    }
                ]
            }
        }


class UserSearchListResponse(BaseModel):
    """Response model for listing user's searches."""

    searches: List[SearchResponse] = Field(..., description="List of searches")
    total: int = Field(..., description="Total number of searches")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")

    class Config:
        json_schema_extra = {
            "example": {
                "searches": [
                    {
                        "id": "search-123",
                        "conversationId": "conv-123",
                        "userId": "user-123",
                        "querySpec": {"diseaseTerms": ["melanoma"]},
                        "resultCount": 10,
                        "executionTimeMs": 1500,
                        "createdAt": "2024-01-01T12:00:00Z"
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0
            }
        }
