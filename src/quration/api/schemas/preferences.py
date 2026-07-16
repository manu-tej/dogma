"""Pydantic schemas for user preferences endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PreferenceResponse(BaseModel):
    """Response model for a user preference."""

    id: str = Field(..., description="Preference ID")
    user_id: str = Field(..., alias="userId", description="User ID")
    preference_type: str = Field(..., alias="preferenceType", description="Type of preference")
    preference_value: Dict[str, Any] = Field(..., alias="preferenceValue", description="Preference value as JSON")
    confidence_score: Optional[float] = Field(None, alias="confidenceScore", description="Confidence score (0.0-1.0)")
    created_at: str = Field(..., alias="createdAt", description="ISO timestamp")
    updated_at: str = Field(..., alias="updatedAt", description="ISO timestamp")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "pref-123",
                "userId": "user-123",
                "preferenceType": "organism",
                "preferenceValue": {"preferred": ["Homo sapiens", "Mus musculus"]},
                "confidenceScore": 0.85,
                "createdAt": "2024-01-01T12:00:00Z",
                "updatedAt": "2024-01-01T12:00:00Z"
            }
        }


class PreferenceCreateRequest(BaseModel):
    """Request model for creating a preference."""

    preference_type: str = Field(
        ...,
        alias="preferenceType",
        description="Type of preference (e.g., organism, platform, disease_area)",
        min_length=1,
        max_length=100
    )
    preference_value: Dict[str, Any] = Field(
        ...,
        alias="preferenceValue",
        description="Preference value as JSON"
    )
    confidence_score: Optional[float] = Field(
        None,
        alias="confidenceScore",
        description="Confidence score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        """Validate confidence score is between 0 and 1."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "preferenceType": "organism",
                "preferenceValue": {
                    "preferred": ["Homo sapiens"],
                    "exclude": []
                },
                "confidenceScore": 0.85
            }
        }


class PreferenceUpdateRequest(BaseModel):
    """Request model for updating a preference."""

    preference_value: Optional[Dict[str, Any]] = Field(
        None,
        alias="preferenceValue",
        description="New preference value"
    )
    confidence_score: Optional[float] = Field(
        None,
        alias="confidenceScore",
        description="New confidence score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        """Validate confidence score is between 0 and 1."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "preferenceValue": {
                    "preferred": ["Homo sapiens", "Mus musculus"],
                    "exclude": ["Rattus norvegicus"]
                },
                "confidenceScore": 0.90
            }
        }


class UserPreferencesResponse(BaseModel):
    """Response model for listing user preferences."""

    preferences: List[PreferenceResponse] = Field(..., description="List of preferences")
    total: int = Field(..., description="Total number of preferences")

    class Config:
        json_schema_extra = {
            "example": {
                "preferences": [
                    {
                        "id": "pref-123",
                        "userId": "user-123",
                        "preferenceType": "organism",
                        "preferenceValue": {"preferred": ["Homo sapiens"]},
                        "confidenceScore": 0.85,
                        "createdAt": "2024-01-01T12:00:00Z",
                        "updatedAt": "2024-01-01T12:00:00Z"
                    }
                ],
                "total": 1
            }
        }


class PreferencesByTypeResponse(BaseModel):
    """Response model for preferences grouped by type."""

    organism: List[PreferenceResponse] = Field(default_factory=list, description="Organism preferences")
    platform: List[PreferenceResponse] = Field(default_factory=list, description="Platform preferences")
    disease_area: List[PreferenceResponse] = Field(
        default_factory=list,
        alias="diseaseArea",
        description="Disease area preferences"
    )
    other: List[PreferenceResponse] = Field(default_factory=list, description="Other preferences")

    class Config:
        populate_by_name = True


class PreferenceSuggestion(BaseModel):
    """Model for a suggested preference."""

    preference_type: str = Field(..., alias="preferenceType", description="Type of preference")
    preference_value: Dict[str, Any] = Field(..., alias="preferenceValue", description="Suggested preference value")
    confidence_score: float = Field(..., alias="confidenceScore", description="AI confidence score (0.0-1.0)")
    rationale: str = Field(..., description="Explanation for why this preference is suggested")
    based_on_searches: int = Field(..., alias="basedOnSearches", description="Number of searches this is based on")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "preferenceType": "organism",
                "preferenceValue": {"preferred": ["Homo sapiens", "Mus musculus"]},
                "confidenceScore": 0.85,
                "rationale": "You've searched for human and mouse datasets in 15 of your last 20 searches",
                "basedOnSearches": 15
            }
        }


class PreferenceSuggestionsResponse(BaseModel):
    """Response model for preference suggestions."""

    suggestions: List[PreferenceSuggestion] = Field(..., description="List of suggested preferences")
    total: int = Field(..., description="Total number of suggestions")

    class Config:
        json_schema_extra = {
            "example": {
                "suggestions": [
                    {
                        "preferenceType": "organism",
                        "preferenceValue": {"preferred": ["Homo sapiens"]},
                        "confidenceScore": 0.85,
                        "rationale": "You frequently search for human datasets",
                        "basedOnSearches": 12
                    }
                ],
                "total": 1
            }
        }


class AcceptSuggestionRequest(BaseModel):
    """Request model for accepting a preference suggestion."""

    preference_type: str = Field(
        ...,
        alias="preferenceType",
        description="Type of preference to accept",
        min_length=1,
        max_length=100
    )
    preference_value: Dict[str, Any] = Field(
        ...,
        alias="preferenceValue",
        description="Preference value to accept"
    )
    confidence_score: float = Field(
        ...,
        alias="confidenceScore",
        description="Confidence score from suggestion",
        ge=0.0,
        le=1.0
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "preferenceType": "organism",
                "preferenceValue": {"preferred": ["Homo sapiens"]},
                "confidenceScore": 0.85
            }
        }
