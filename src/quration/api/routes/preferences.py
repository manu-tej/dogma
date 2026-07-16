"""API routes for user preferences management."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from quration.api.dependencies import get_async_session, get_current_user_id
from quration.api.schemas.preferences import (
    AcceptSuggestionRequest,
    PreferenceCreateRequest,
    PreferenceResponse,
    PreferenceSuggestion,
    PreferenceSuggestionsResponse,
    PreferenceUpdateRequest,
    UserPreferencesResponse,
)
from quration.repositories.user import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["User Preferences"])


@router.get(
    "/users/{user_id}/preferences",
    response_model=UserPreferencesResponse,
    summary="Get user preferences",
    description="Retrieve all preferences for a user"
)
async def get_user_preferences(
    user_id: UUID = Path(..., description="User UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all preferences for a user.

    Args:
        user_id: User UUID from path
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        User preferences

    Raises:
        HTTPException: 403 if user doesn't match authenticated user
    """
    # Verify user can access these preferences
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another user's preferences"
        )

    try:
        repo = UserRepository(session)
        preferences = await repo.get_user_preferences(user_id, use_cache=True)

        preference_responses = [
            PreferenceResponse(
                id=str(pref.id),
                user_id=str(pref.user_id),
                preference_type=pref.preference_type,
                preference_value=pref.preference_value,
                confidence_score=pref.confidence_score,
                created_at=pref.created_at.isoformat(),
                updated_at=pref.updated_at.isoformat()
            )
            for pref in preferences
        ]

        return UserPreferencesResponse(
            preferences=preference_responses,
            total=len(preference_responses)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user preferences: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.put(
    "/users/{user_id}/preferences",
    response_model=PreferenceResponse,
    summary="Create or update user preference",
    description="Create a new preference or update an existing one by type"
)
async def upsert_user_preference(
    user_id: UUID = Path(..., description="User UUID"),
    request: PreferenceCreateRequest = ...,
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Create or update a user preference.

    If a preference of the same type exists, it will be updated.
    Otherwise, a new preference will be created.

    Args:
        user_id: User UUID from path
        request: Preference creation request
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        Created or updated preference

    Raises:
        HTTPException: 403 if user doesn't match authenticated user
    """
    # Verify user can modify these preferences
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify another user's preferences"
        )

    try:
        repo = UserRepository(session)

        # Check if preference exists
        existing = await repo.get_preference_by_type(
            user_id=user_id,
            preference_type=request.preference_type
        )

        if existing:
            # Update existing preference
            preference = await repo.update_preference(
                preference_id=existing.id,
                preference_value=request.preference_value,
                confidence_score=request.confidence_score
            )
        else:
            # Create new preference
            preference = await repo.save_preference(
                user_id=user_id,
                preference_type=request.preference_type,
                preference_value=request.preference_value,
                confidence_score=request.confidence_score
            )

        await session.commit()

        return PreferenceResponse(
            id=str(preference.id),
            user_id=str(preference.user_id),
            preference_type=preference.preference_type,
            preference_value=preference.preference_value,
            confidence_score=preference.confidence_score,
            created_at=preference.created_at.isoformat(),
            updated_at=preference.updated_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert preference: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/users/{user_id}/preferences/{preference_type}",
    response_model=PreferenceResponse,
    summary="Get preference by type",
    description="Get a specific preference by type"
)
async def get_preference_by_type(
    user_id: UUID = Path(..., description="User UUID"),
    preference_type: str = Path(..., description="Preference type"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific preference by type.

    Args:
        user_id: User UUID
        preference_type: Type of preference
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        Preference

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found
    """
    # Verify user can access these preferences
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another user's preferences"
        )

    try:
        repo = UserRepository(session)
        preference = await repo.get_preference_by_type(
            user_id=user_id,
            preference_type=preference_type
        )

        if not preference:
            raise HTTPException(
                status_code=404,
                detail=f"Preference type '{preference_type}' not found for user"
            )

        return PreferenceResponse(
            id=str(preference.id),
            user_id=str(preference.user_id),
            preference_type=preference.preference_type,
            preference_value=preference.preference_value,
            confidence_score=preference.confidence_score,
            created_at=preference.created_at.isoformat(),
            updated_at=preference.updated_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preference: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/users/{user_id}/preferences/{preference_id}",
    status_code=204,
    summary="Delete user preference",
    description="Delete a specific user preference"
)
async def delete_user_preference(
    user_id: UUID = Path(..., description="User UUID"),
    preference_id: UUID = Path(..., description="Preference UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a user preference.

    Args:
        user_id: User UUID
        preference_id: Preference UUID
        current_user_id: Authenticated user UUID
        session: Database session

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found
    """
    # Verify user can modify these preferences
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete another user's preferences"
        )

    try:
        repo = UserRepository(session)
        success = await repo.delete_preference(preference_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Preference {preference_id} not found"
            )

        await session.commit()
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete preference: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/users/{user_id}/preferences/suggestions",
    response_model=PreferenceSuggestionsResponse,
    summary="Get preference suggestions",
    description="Get AI-suggested preferences based on user's search history"
)
async def get_preference_suggestions(
    user_id: UUID = Path(..., description="User UUID"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence score threshold"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Generate preference suggestions based on user's search patterns.

    Analyzes recent search history to identify patterns and suggest preferences
    that the user might want to save.

    Args:
        user_id: User UUID
        min_confidence: Minimum confidence score for suggestions (default: 0.5)
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        List of preference suggestions

    Raises:
        HTTPException: 403 if unauthorized
    """
    # Verify user can access suggestions
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another user's preference suggestions"
        )

    try:
        repo = UserRepository(session)

        # Analyze search patterns
        patterns = await repo.analyze_search_patterns(user_id, limit=50)

        if not patterns:
            return PreferenceSuggestionsResponse(suggestions=[], total=0)

        # Get existing preferences to avoid duplicates
        existing_prefs = await repo.get_user_preferences(user_id)
        existing_types = {pref.preference_type for pref in existing_prefs}

        # Generate suggestions
        suggestions = []

        for pref_type, pattern_data in patterns.items():
            # Skip if user already has this preference type
            if pref_type in existing_types:
                continue

            frequency = pattern_data["frequency"]
            values = pattern_data["values"]
            counts = pattern_data["counts"]
            total_searches = pattern_data["total_searches"]

            # Calculate confidence based on frequency and consistency
            # Higher confidence if user consistently searches for the same values
            top_value_count = counts.get(values[0], 0) if values else 0
            consistency = top_value_count / total_searches if total_searches > 0 else 0
            confidence = min(0.95, (frequency * 0.6) + (consistency * 0.4))

            # Only suggest if confidence meets threshold
            if confidence >= min_confidence:
                # Build preference value
                preference_value = {"preferred": values[:3]}  # Top 3 values

                # Generate rationale
                if len(values) == 1:
                    rationale = f"You've searched for {values[0]} in {top_value_count} of your last {total_searches} searches"
                else:
                    rationale = f"You frequently search for {', '.join(values[:2])} and similar {pref_type} values ({int(frequency * 100)}% of searches)"

                suggestions.append(
                    PreferenceSuggestion(
                        preference_type=pref_type,
                        preference_value=preference_value,
                        confidence_score=round(confidence, 2),
                        rationale=rationale,
                        based_on_searches=total_searches
                    )
                )

        # Sort by confidence score descending
        suggestions.sort(key=lambda x: x.confidence_score, reverse=True)

        return PreferenceSuggestionsResponse(
            suggestions=suggestions,
            total=len(suggestions)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate preference suggestions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/users/{user_id}/preferences/accept",
    response_model=PreferenceResponse,
    summary="Accept a preference suggestion",
    description="Accept and save a suggested preference"
)
async def accept_preference_suggestion(
    user_id: UUID = Path(..., description="User UUID"),
    request: AcceptSuggestionRequest = ...,
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Accept a preference suggestion and save it.

    This endpoint creates or updates a preference based on an accepted suggestion.

    Args:
        user_id: User UUID
        request: Accepted suggestion data
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        Created or updated preference

    Raises:
        HTTPException: 403 if unauthorized
    """
    # Verify user can modify preferences
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify another user's preferences"
        )

    try:
        repo = UserRepository(session)

        # Check if preference already exists
        existing = await repo.get_preference_by_type(
            user_id=user_id,
            preference_type=request.preference_type
        )

        if existing:
            # Update existing preference
            preference = await repo.update_preference(
                preference_id=existing.id,
                preference_value=request.preference_value,
                confidence_score=request.confidence_score
            )
        else:
            # Create new preference
            preference = await repo.save_preference(
                user_id=user_id,
                preference_type=request.preference_type,
                preference_value=request.preference_value,
                confidence_score=request.confidence_score
            )

        await session.commit()

        logger.info(
            f"User {user_id} accepted preference suggestion: {request.preference_type}"
        )

        return PreferenceResponse(
            id=str(preference.id),
            user_id=str(preference.user_id),
            preference_type=preference.preference_type,
            preference_value=preference.preference_value,
            confidence_score=preference.confidence_score,
            created_at=preference.created_at.isoformat(),
            updated_at=preference.updated_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to accept preference suggestion: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
