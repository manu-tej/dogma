"""API routes for search management."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from quration.api.dependencies import (
    get_async_session,
    get_context_service,
    get_current_user_id,
)
from quration.api.schemas.search import (
    SearchCreateRequest,
    SearchResponse,
    SearchResultResponse,
    SearchWithResultsResponse,
    UserSearchListResponse,
)
from quration.repositories.search import SearchRepository
from quration.services.context_service import ContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Search Management"])

# Backward compatibility router for /context/* endpoints
context_router = APIRouter(prefix="/context", tags=["Search Management (Legacy)"])


@router.post(
    "/searches",
    response_model=SearchResponse,
    status_code=201,
    summary="Save a search with results",
    description="Save a search query and its results for future reference"
)
async def save_search(
    request: SearchCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
    session: AsyncSession = Depends(get_async_session),
):
    """Save a search with its results.

    This endpoint persists a search query along with all its results
    to enable context restoration and search history.

    Args:
        request: Search creation request with query spec and results
        user_id: Authenticated user UUID
        context_service: Context service instance
        session: Database session

    Returns:
        Created search

    Raises:
        HTTPException: 404 if conversation not found
    """
    try:
        # Verify conversation exists
        conversation_id = UUID(request.conversation_id)

        # Convert results to format expected by service
        results = [
            {
                "dataset_id": result.dataset_id,
                "rank": result.rank,
                "metadata": result.metadata or {}
            }
            for result in request.results
        ]

        # Save search with results
        search = await context_service.save_search_with_results(
            conversation_id=conversation_id,
            user_id=user_id,
            query_spec=request.query_spec,
            results=results,
            execution_time_ms=request.execution_time_ms
        )

        return SearchResponse(
            id=str(search.id),
            conversation_id=str(search.conversation_id),
            user_id=str(search.user_id),
            query_spec=search.query_spec,
            result_count=search.result_count,
            execution_time_ms=search.execution_time_ms,
            created_at=search.created_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save search: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/searches/{search_id}",
    response_model=SearchWithResultsResponse,
    summary="Get search details",
    description="Retrieve a search with all its results"
)
async def get_search(
    search_id: UUID = Path(..., description="Search UUID"),
    session: AsyncSession = Depends(get_async_session),
):
    """Get search details with results.

    Args:
        search_id: Search UUID
        session: Database session

    Returns:
        Search with results

    Raises:
        HTTPException: 404 if search not found
    """
    try:
        repo = SearchRepository(session)
        search = await repo.get_search(search_id, use_cache=True)

        if not search:
            raise HTTPException(
                status_code=404,
                detail=f"Search {search_id} not found"
            )

        # Get results
        results = await repo.get_search_results(search_id)

        search_response = SearchResponse(
            id=str(search.id),
            conversation_id=str(search.conversation_id),
            user_id=str(search.user_id),
            query_spec=search.query_spec,
            result_count=search.result_count,
            execution_time_ms=search.execution_time_ms,
            created_at=search.created_at.isoformat()
        )

        result_responses = [
            SearchResultResponse(
                id=str(result.id),
                dataset_id=result.dataset_id,
                rank=result.rank,
                metadata=result.metadata,
                created_at=result.created_at.isoformat()
            )
            for result in results
        ]

        return SearchWithResultsResponse(
            search=search_response,
            results=result_responses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/searches/user/{user_id}",
    response_model=UserSearchListResponse,
    summary="List user's searches",
    description="Get paginated list of searches for a user"
)
async def list_user_searches(
    user_id: UUID = Path(..., description="User UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100, description="Maximum searches to return"),
    offset: int = Query(0, ge=0, description="Number of searches to skip"),
    conversation_id: str = Query(None, alias="conversationId", description="Optional conversation filter"),
    session: AsyncSession = Depends(get_async_session),
):
    """List searches for a user.

    Args:
        user_id: User UUID from path
        current_user_id: Authenticated user UUID
        limit: Maximum searches to return
        offset: Number to skip for pagination
        conversation_id: Optional filter by conversation
        session: Database session

    Returns:
        Paginated list of searches

    Raises:
        HTTPException: 403 if user doesn't match authenticated user
    """
    # Verify user can access these searches
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another user's searches"
        )

    try:
        repo = SearchRepository(session)

        # Parse conversation_id if provided
        conv_id = UUID(conversation_id) if conversation_id else None

        searches = await repo.get_user_searches(
            user_id=user_id,
            limit=limit,
            offset=offset,
            conversation_id=conv_id
        )

        # Get total count
        total = await repo.count_user_searches(
            user_id=user_id,
            conversation_id=conv_id
        )

        search_responses = [
            SearchResponse(
                id=str(search.id),
                conversation_id=str(search.conversation_id),
                user_id=str(search.user_id),
                query_spec=search.query_spec,
                result_count=search.result_count,
                execution_time_ms=search.execution_time_ms,
                created_at=search.created_at.isoformat()
            )
            for search in searches
        ]

        return UserSearchListResponse(
            searches=search_responses,
            total=total,
            limit=limit,
            offset=offset
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list user searches: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/searches/dataset/{dataset_id}",
    response_model=List[SearchResponse],
    summary="Find searches by dataset",
    description="Find searches that returned a specific dataset"
)
async def find_searches_by_dataset(
    dataset_id: str = Path(..., description="Dataset ID (e.g., GSE123456)"),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=50, description="Maximum searches to return"),
    session: AsyncSession = Depends(get_async_session),
):
    """Find searches that returned a specific dataset.

    Useful for understanding how users found a particular dataset.

    Args:
        dataset_id: Dataset ID
        user_id: Authenticated user UUID
        limit: Maximum searches to return
        session: Database session

    Returns:
        List of searches containing this dataset
    """
    try:
        repo = SearchRepository(session)
        searches = await repo.get_dataset_searches(
            dataset_id=dataset_id,
            user_id=user_id,
            limit=limit
        )

        return [
            SearchResponse(
                id=str(search.id),
                conversation_id=str(search.conversation_id),
                user_id=str(search.user_id),
                query_spec=search.query_spec,
                result_count=search.result_count,
                execution_time_ms=search.execution_time_ms,
                created_at=search.created_at.isoformat()
            )
            for search in searches
        ]

    except Exception as e:
        logger.error(f"Failed to find searches by dataset: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Backward compatibility alias
@context_router.post(
    "/searches",
    response_model=SearchResponse,
    status_code=201,
    summary="Save a search with results (Legacy endpoint)",
    description="Legacy endpoint - use /api/v1/searches instead"
)
async def save_search_legacy(
    request: SearchCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    context_service: ContextService = Depends(get_context_service),
    session: AsyncSession = Depends(get_async_session),
):
    """Legacy endpoint that redirects to /api/v1/searches."""
    return await save_search(request, user_id, context_service, session)
