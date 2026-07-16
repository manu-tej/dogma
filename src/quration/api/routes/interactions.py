"""API routes for interaction tracking."""

import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from quration.api.dependencies import (
    get_async_session,
    get_context_service,
    get_current_user_id,
)
from quration.api.schemas.interaction import (
    DatasetConversationItem,
    DatasetConversationsResponse,
    DatasetInteractionHistoryResponse,
    InteractionHistoryResponse,
    InteractionRecordRequest,
    InteractionResponse,
    InteractionStatsResponse,
    RecalledDatasetItem,
    RecalledDatasetsResponse,
)
from quration.repositories.interaction import InteractionRepository
from quration.services.context_service import ContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Interaction Tracking"])

# Backward compatibility router for /context/* endpoints
context_router = APIRouter(prefix="/context", tags=["Interaction Tracking (Legacy)"])


@router.post(
    "/interactions/{dataset_id}",
    response_model=InteractionResponse,
    status_code=201,
    summary="Record dataset interaction",
    description="Record a user interaction with a dataset (view, analyze, download)"
)
async def record_interaction(
    dataset_id: str = Path(..., description="Dataset ID (e.g., GSE123456)"),
    request: InteractionRecordRequest = ...,
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
    session: AsyncSession = Depends(get_async_session),
):
    """Record a user interaction with a dataset.

    This endpoint tracks user actions like viewing, analyzing, or downloading datasets
    to build interaction history and preferences.

    Args:
        dataset_id: Dataset ID from path (must match request body)
        request: Interaction recording request
        user_id: Authenticated user UUID
        context_service: Context service instance
        session: Database session

    Returns:
        Created interaction

    Raises:
        HTTPException: 400 if dataset IDs don't match
    """
    # Verify dataset_id matches
    if dataset_id != request.dataset_id:
        raise HTTPException(
            status_code=400,
            detail=f"Path dataset_id ({dataset_id}) does not match body dataset_id ({request.dataset_id})"
        )

    try:
        # Parse optional UUIDs
        conversation_id = UUID(request.conversation_id) if request.conversation_id else None
        search_id = UUID(request.search_id) if request.search_id else None

        # Record interaction
        interaction = await context_service.track_dataset_interaction(
            user_id=user_id,
            dataset_id=request.dataset_id,
            interaction_type=request.interaction_type,
            conversation_id=conversation_id,
            search_id=search_id,
            metadata=request.metadata or {}
        )

        return InteractionResponse(
            id=str(interaction.id),
            user_id=str(interaction.user_id),
            dataset_id=interaction.dataset_id,
            interaction_type=interaction.interaction_type,
            conversation_id=str(interaction.conversation_id) if interaction.conversation_id else None,
            search_id=str(interaction.search_id) if interaction.search_id else None,
            created_at=interaction.created_at.isoformat(),
            metadata=interaction.metadata
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to record interaction: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/interactions/history",
    response_model=InteractionHistoryResponse,
    summary="Get interaction history",
    description="Get paginated interaction history for the authenticated user"
)
async def get_interaction_history(
    user_id: UUID = Depends(get_current_user_id),
    dataset_id: str = Query(None, alias="datasetId", description="Optional dataset filter"),
    interaction_type: str = Query(None, alias="interactionType", description="Optional type filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum interactions to return"),
    offset: int = Query(0, ge=0, description="Number of interactions to skip"),
    session: AsyncSession = Depends(get_async_session),
):
    """Get interaction history for a user.

    Args:
        user_id: Authenticated user UUID
        dataset_id: Optional filter by dataset
        interaction_type: Optional filter by interaction type
        limit: Maximum interactions to return
        offset: Number to skip for pagination
        session: Database session

    Returns:
        Paginated interaction history
    """
    try:
        repo = InteractionRepository(session)
        interactions = await repo.get_user_interactions(
            user_id=user_id,
            dataset_id=dataset_id,
            interaction_type=interaction_type,
            limit=limit,
            offset=offset
        )

        # Get total count (simplified - would need a count method in repo)
        # For now, just use len of results as approximate
        total = len(interactions) + offset if len(interactions) == limit else len(interactions) + offset

        interaction_responses = [
            InteractionResponse(
                id=str(inter.id),
                user_id=str(inter.user_id),
                dataset_id=inter.dataset_id,
                interaction_type=inter.interaction_type,
                conversation_id=str(inter.conversation_id) if inter.conversation_id else None,
                search_id=str(inter.search_id) if inter.search_id else None,
                created_at=inter.created_at.isoformat(),
                metadata=inter.metadata
            )
            for inter in interactions
        ]

        return InteractionHistoryResponse(
            interactions=interaction_responses,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to get interaction history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/interactions/dataset/{dataset_id}",
    response_model=DatasetInteractionHistoryResponse,
    summary="Get dataset interaction history",
    description="Get user's interaction history with a specific dataset"
)
async def get_dataset_interaction_history(
    dataset_id: str = Path(..., description="Dataset ID (e.g., GSE123456)"),
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
):
    """Get user's interaction history with a specific dataset.

    Returns comprehensive history including:
    - Whether user has viewed the dataset
    - First view timestamp
    - All interactions with the dataset
    - Related searches that returned this dataset

    Args:
        dataset_id: Dataset ID
        user_id: Authenticated user UUID
        context_service: Context service instance

    Returns:
        Dataset interaction history
    """
    try:
        history = await context_service.get_dataset_history(
            dataset_id=dataset_id,
            user_id=user_id
        )

        # Transform interactions
        interaction_responses = [
            InteractionResponse(
                id=inter["id"],
                user_id=str(user_id),
                dataset_id=dataset_id,
                interaction_type=inter["type"],
                conversation_id=inter["conversation_id"],
                search_id=None,
                created_at=inter["created_at"],
                metadata={}
            )
            for inter in history["interactions"]
        ]

        return DatasetInteractionHistoryResponse(
            dataset_id=history["dataset_id"],
            has_viewed=history["has_viewed"],
            first_viewed_at=history["first_viewed_at"],
            interaction_count=history["interaction_count"],
            interactions=interaction_responses,
            related_searches=history["related_searches"]
        )

    except Exception as e:
        logger.error(f"Failed to get dataset interaction history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/interactions/stats",
    response_model=InteractionStatsResponse,
    summary="Get interaction statistics",
    description="Get aggregate interaction statistics for the authenticated user"
)
async def get_interaction_stats(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Get interaction statistics for a user.

    Returns aggregate statistics including:
    - Total interactions
    - Breakdown by interaction type
    - Number of unique datasets interacted with

    Args:
        user_id: Authenticated user UUID
        session: Database session

    Returns:
        Interaction statistics
    """
    try:
        repo = InteractionRepository(session)
        stats = await repo.get_interaction_stats(user_id)

        return InteractionStatsResponse(
            total_interactions=stats["total_interactions"],
            view_count=stats["view_count"],
            analyze_count=stats["analyze_count"],
            download_count=stats["download_count"],
            unique_datasets=stats["unique_datasets"]
        )

    except Exception as e:
        logger.error(f"Failed to get interaction stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/interactions/datasets/viewed",
    response_model=List[str],
    summary="Get viewed datasets",
    description="Get list of dataset IDs the user has viewed"
)
async def get_viewed_datasets(
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=500, description="Maximum dataset IDs to return"),
    offset: int = Query(0, ge=0, description="Number to skip"),
    session: AsyncSession = Depends(get_async_session),
):
    """Get list of datasets the user has viewed.

    Returns dataset IDs in order of most recent interaction.

    Args:
        user_id: Authenticated user UUID
        limit: Maximum dataset IDs to return
        offset: Number to skip for pagination
        session: Database session

    Returns:
        List of dataset IDs
    """
    try:
        repo = InteractionRepository(session)
        dataset_ids = await repo.get_user_viewed_datasets(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return list(dataset_ids)

    except Exception as e:
        logger.error(f"Failed to get viewed datasets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/datasets/recalled",
    response_model=RecalledDatasetsResponse,
    summary="Get recalled datasets across conversations",
    description="Get recently viewed datasets across all user conversations for cross-conversation recall"
)
async def get_recalled_datasets(
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Maximum datasets to return"),
    since: str = Query(None, description="Optional ISO datetime filter (e.g., 2024-01-01T00:00:00Z)"),
    context_service: ContextService = Depends(get_context_service),
):
    """Get recently viewed datasets across all conversations.

    This endpoint enables "show me that dataset I looked at last week" type queries
    by returning datasets ordered by most recent interaction with conversation context.

    Args:
        user_id: Authenticated user UUID
        limit: Maximum datasets to return (default 10, max 100)
        since: Optional ISO datetime string to filter interactions after this time
        context_service: Context service instance

    Returns:
        List of datasets with interaction details and conversation context

    Example:
        GET /api/v1/datasets/recalled?limit=20&since=2024-01-01T00:00:00Z
    """
    try:
        # Parse since parameter if provided
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid datetime format for 'since': {str(e)}. Use ISO format (e.g., 2024-01-01T00:00:00Z)"
                )

        # Get recalled datasets
        datasets = await context_service.get_recalled_datasets(
            user_id=user_id,
            limit=limit,
            since=since_dt,
        )

        # Transform to response format
        dataset_items = [
            RecalledDatasetItem(
                datasetId=ds["dataset_id"],
                lastInteractionAt=ds["last_interaction_at"].isoformat(),
                interactionCount=ds["interaction_count"],
                lastInteractionType=ds["last_interaction_type"],
                conversationId=str(ds["conversation_id"]) if ds["conversation_id"] else None,
                conversationTitle=ds["conversation_title"],
            )
            for ds in datasets
        ]

        return RecalledDatasetsResponse(
            datasets=dataset_items,
            total=len(dataset_items),
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recalled datasets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/datasets/{dataset_id}/conversations",
    response_model=DatasetConversationsResponse,
    summary="Find conversations containing a dataset",
    description="Get all conversations where user interacted with a specific dataset"
)
async def get_dataset_conversations(
    dataset_id: str = Path(..., description="Dataset ID (e.g., GSE123456, PRIDE12345)"),
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
):
    """Find all conversations containing a specific dataset.

    Returns all conversations where the user has interacted with the specified
    dataset, including interaction details and conversation metadata.

    Args:
        dataset_id: Dataset ID (can be GEO ID, PRIDE ID, etc.)
        user_id: Authenticated user UUID
        context_service: Context service instance

    Returns:
        List of conversations with interaction details

    Example:
        GET /api/v1/datasets/GSE123456/conversations
    """
    try:
        # Get conversations
        conversations = await context_service.get_dataset_conversations(
            dataset_id=dataset_id,
            user_id=user_id,
        )

        # Transform to response format
        conversation_items = [
            DatasetConversationItem(
                conversationId=str(conv["conversation_id"]),
                conversationTitle=conv["conversation_title"],
                firstInteractionAt=conv["first_interaction_at"].isoformat(),
                interactionCount=conv["interaction_count"],
                interactionTypes=conv["interaction_types"],
            )
            for conv in conversations
        ]

        return DatasetConversationsResponse(
            datasetId=dataset_id,
            conversations=conversation_items,
            totalConversations=len(conversation_items),
        )

    except Exception as e:
        logger.error(f"Failed to get conversations for dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Backward compatibility aliases
@context_router.post(
    "/interactions",
    response_model=InteractionResponse,
    status_code=201,
    summary="Record dataset interaction (Legacy endpoint)",
    description="Legacy endpoint - use /api/v1/interactions/{dataset_id} instead"
)
async def record_interaction_legacy(
    request: InteractionRecordRequest,
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
    session: AsyncSession = Depends(get_async_session),
):
    """Legacy endpoint that redirects to /api/v1/interactions/{dataset_id}."""
    return await record_interaction(request.dataset_id, request, user_id, context_service, session)


@context_router.get(
    "/datasets/{dataset_id}/history",
    response_model=DatasetInteractionHistoryResponse,
    summary="Get dataset interaction history (Legacy endpoint)",
    description="Legacy endpoint - use /api/v1/interactions/dataset/{dataset_id} instead"
)
async def get_dataset_history_legacy(
    dataset_id: str = Path(..., description="Dataset ID (e.g., GSE123456)"),
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
):
    """Legacy endpoint that redirects to /api/v1/interactions/dataset/{dataset_id}."""
    return await get_dataset_interaction_history(dataset_id, user_id, context_service)
