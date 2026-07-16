"""API routes for conversation context management."""

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
from quration.api.schemas.context import (
    AddTagsRequest,
    ConversationContextResponse,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationSearchResponse,
    ConversationStateResponse,
    InteractionBreakdown,
    InteractionSummaryResponse,
    MessageCreateRequest,
    MessageResponse,
    RecentConversationSummary,
    SearchResultSummary,
    SearchSummaryResponse,
    SearchWithResultsSummary,
    UserContextSummaryResponse,
    UserStatisticsResponse,
)
from quration.repositories.conversation import ConversationRepository
from quration.services.context_service import ContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Context Management"])


@router.get(
    "/conversations/{conversation_id}/context",
    response_model=ConversationContextResponse,
    summary="Get full conversation context",
    description="Retrieve complete conversation context including messages, searches, and interactions"
)
async def get_conversation_context(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    context_service: ContextService = Depends(get_context_service),
):
    """Get full conversation context.

    This endpoint returns:
    - Conversation metadata
    - All messages in the conversation
    - All searches performed
    - All interactions with datasets

    Args:
        conversation_id: Conversation UUID
        context_service: Context service instance

    Returns:
        Complete conversation context

    Raises:
        HTTPException: 404 if conversation not found
    """
    try:
        context = await context_service.get_conversation_context(conversation_id)

        if not context:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Transform to response model
        return ConversationContextResponse(
            conversation=ConversationResponse(**context["conversation"]),
            messages=[MessageResponse(**msg) for msg in context["messages"]],
            searches=[SearchSummaryResponse(**search) for search in context["searches"]],
            interactions=[InteractionSummaryResponse(**inter) for inter in context["interactions"]]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation context: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/conversations/{conversation_id}/restore",
    response_model=ConversationStateResponse,
    summary="Restore conversation state",
    description="Restore complete conversation state including search results for UI rendering"
)
async def restore_conversation_state(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    context_service: ContextService = Depends(get_context_service),
):
    """Restore complete conversation state.

    This endpoint returns everything needed to restore a conversation in the UI:
    - Conversation metadata
    - All messages
    - All searches with their full results
    - All interactions

    Args:
        conversation_id: Conversation UUID
        context_service: Context service instance

    Returns:
        Complete conversation state

    Raises:
        HTTPException: 404 if conversation not found
    """
    try:
        state = await context_service.restore_conversation_state(conversation_id)

        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Transform searches with results
        searches_with_results = []
        for search_dict in state["searches"]:
            results = [
                SearchResultSummary(**result)
                for result in search_dict.get("results", [])
            ]
            search_dict_copy = search_dict.copy()
            search_dict_copy["results"] = results
            searches_with_results.append(SearchWithResultsSummary(**search_dict_copy))

        return ConversationStateResponse(
            conversation=ConversationResponse(**state["conversation"]),
            messages=[MessageResponse(**msg) for msg in state["messages"]],
            searches=searches_with_results,
            interactions=[InteractionSummaryResponse(**inter) for inter in state["interactions"]]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore conversation state: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/conversations",
    response_model=List[ConversationResponse],
    summary="List user conversations",
    description="Get list of conversations for the authenticated user"
)
async def list_conversations(
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100, description="Maximum conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    session: AsyncSession = Depends(get_async_session),
):
    """List conversations for a user.

    Args:
        user_id: User UUID from auth
        limit: Maximum conversations to return
        offset: Number to skip for pagination
        session: Database session

    Returns:
        List of conversations
    """
    try:
        repo = ConversationRepository(session)
        conversations = await repo.list_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset,
            include_messages=False
        )

        return [
            ConversationResponse(
                id=str(conv.id),
                user_id=str(conv.user_id),
                title=conv.title,
                tags=conv.tags,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                metadata=conv.metadata
            )
            for conv in conversations
        ]

    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=201,
    summary="Create new conversation",
    description="Create a new conversation for the authenticated user"
)
async def create_conversation(
    request: ConversationCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new conversation.

    Args:
        request: Conversation creation request
        user_id: User UUID from auth
        session: Database session

    Returns:
        Created conversation
    """
    try:
        repo = ConversationRepository(session)
        conversation = await repo.create_conversation(
            user_id=user_id,
            title=request.title,
            metadata=request.metadata or {}
        )
        await session.commit()

        return ConversationResponse(
            id=str(conversation.id),
            user_id=str(conversation.user_id),
            title=conversation.title,
            tags=conversation.tags,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            metadata=conversation.metadata
        )

    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    summary="Add message to conversation",
    description="Add a new message to an existing conversation"
)
async def add_message(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    request: MessageCreateRequest = ...,
    session: AsyncSession = Depends(get_async_session),
):
    """Add a message to a conversation.

    Args:
        conversation_id: Conversation UUID
        request: Message creation request
        session: Database session

    Returns:
        Created message
    """
    try:
        repo = ConversationRepository(session)

        # Verify conversation exists
        conversation = await repo.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        message = await repo.add_message(
            conversation_id=conversation_id,
            role=request.role,
            content=request.content,
            metadata=request.metadata or {}
        )
        await session.commit()

        return MessageResponse(
            id=str(message.id),
            role=message.role,
            content=message.content,
            created_at=message.created_at.isoformat(),
            metadata=message.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details",
    description="Get details of a specific conversation"
)
async def get_conversation(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    session: AsyncSession = Depends(get_async_session),
):
    """Get conversation details.

    Args:
        conversation_id: Conversation UUID
        session: Database session

    Returns:
        Conversation details

    Raises:
        HTTPException: 404 if not found
    """
    try:
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        return ConversationResponse(
            id=str(conversation.id),
            user_id=str(conversation.user_id),
            title=conversation.title,
            tags=conversation.tags,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            metadata=conversation.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/users/{user_id}/summary",
    response_model=UserContextSummaryResponse,
    summary="Get user context summary",
    description="Get user's context summary with statistics and recent activity"
)
async def get_user_summary(
    user_id: UUID = Path(..., description="User UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Get user context summary.

    Returns:
    - User statistics (conversations, searches, interactions)
    - Recent conversations
    - Interaction breakdown by type

    Args:
        user_id: User UUID from path
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        User context summary

    Raises:
        HTTPException: 403 if user doesn't match authenticated user
    """
    # Verify user can access this summary
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another user's summary"
        )

    try:
        from quration.repositories.conversation import ConversationRepository
        from quration.repositories.search import SearchRepository
        from quration.repositories.interaction import InteractionRepository

        conv_repo = ConversationRepository(session)
        search_repo = SearchRepository(session)
        interaction_repo = InteractionRepository(session)

        # Get statistics
        conversations = await conv_repo.list_user_conversations(user_id, limit=1000, offset=0, include_messages=False)
        total_conversations = len(conversations)

        searches = await search_repo.get_user_searches(user_id, limit=1000, offset=0)
        total_searches = len(searches)

        interaction_stats = await interaction_repo.get_interaction_stats(user_id)

        # Get recent conversations (top 5)
        recent_convs = conversations[:5]
        recent_conversations = [
            RecentConversationSummary(
                id=str(conv.id),
                title=conv.title or "Untitled",
                updated_at=conv.updated_at.isoformat()
            )
            for conv in recent_convs
        ]

        # Build response
        return UserContextSummaryResponse(
            user_id=str(user_id),
            statistics=UserStatisticsResponse(
                total_conversations=total_conversations,
                total_searches=total_searches,
                total_interactions=interaction_stats["total_interactions"],
                unique_datasets_viewed=interaction_stats["unique_datasets"],
                saved_preferences=0  # TODO: Implement preferences counting
            ),
            recent_conversations=recent_conversations,
            interaction_breakdown=InteractionBreakdown(
                views=interaction_stats["view_count"],
                analyses=interaction_stats["analyze_count"],
                downloads=interaction_stats["download_count"]
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/users/{user_id}/conversations",
    response_model=List[ConversationResponse],
    summary="List user's conversations",
    description="Get list of conversations for a specific user"
)
async def list_user_conversations(
    user_id: UUID = Path(..., description="User UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100, description="Maximum conversations to return"),
    include_archived: bool = Query(False, alias="includeArchived", description="Include archived conversations"),
    session: AsyncSession = Depends(get_async_session),
):
    """List conversations for a user.

    Args:
        user_id: User UUID from path
        current_user_id: Authenticated user UUID
        limit: Maximum conversations to return
        include_archived: Whether to include archived conversations
        session: Database session

    Returns:
        List of conversations

    Raises:
        HTTPException: 403 if user doesn't match authenticated user
    """
    # Verify user can access these conversations
    if user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access another user's conversations"
        )

    try:
        repo = ConversationRepository(session)
        conversations = await repo.list_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=0,
            include_messages=False
        )

        # Filter archived if needed
        if not include_archived:
            conversations = [
                conv for conv in conversations
                if not conv.metadata.get("archived", False)
            ]

        return [
            ConversationResponse(
                id=str(conv.id),
                user_id=str(conv.user_id),
                title=conv.title,
                tags=conv.tags,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                metadata=conv.metadata
            )
            for conv in conversations
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list user conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/conversations/{conversation_id}/archive",
    response_model=ConversationResponse,
    summary="Archive a conversation",
    description="Mark a conversation as archived"
)
async def archive_conversation(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Archive a conversation.

    Sets the 'archived' flag in conversation metadata.

    Args:
        conversation_id: Conversation UUID
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        Updated conversation

    Raises:
        HTTPException: 404 if conversation not found, 403 if user doesn't own it
    """
    try:
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Verify ownership
        if conversation.user_id != current_user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot archive another user's conversation"
            )

        # Update metadata to mark as archived
        metadata = conversation.metadata or {}
        metadata["archived"] = True
        metadata["archived_at"] = datetime.utcnow().isoformat()

        await repo.update_conversation(
            conversation_id=conversation_id,
            title=conversation.title,
            metadata=metadata
        )
        await session.commit()

        # Fetch updated conversation
        updated = await repo.get_by_id(conversation_id)

        return ConversationResponse(
            id=str(updated.id),
            user_id=str(updated.user_id),
            title=updated.title,
            created_at=updated.created_at.isoformat(),
            updated_at=updated.updated_at.isoformat(),
            metadata=updated.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive conversation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    summary="Delete a conversation",
    description="Permanently delete a conversation and all its messages"
)
async def delete_conversation(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a conversation.

    Permanently deletes the conversation and all associated messages.
    This action cannot be undone.

    Args:
        conversation_id: Conversation UUID
        current_user_id: Authenticated user UUID
        session: Database session

    Raises:
        HTTPException: 404 if conversation not found, 403 if user doesn't own it
    """
    try:
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Verify ownership
        if conversation.user_id != current_user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete another user's conversation"
            )

        # Delete conversation (cascade will delete messages)
        await repo.delete_conversation(conversation_id)
        await session.commit()

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/conversations/{conversation_id}/tags",
    response_model=ConversationResponse,
    summary="Add tags to conversation",
    description="Add one or more tags to a conversation for organization and search"
)
async def add_conversation_tags(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    request: AddTagsRequest = ...,
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Add tags to a conversation.

    Tags are normalized to lowercase and validated:
    - Must be alphanumeric with hyphens
    - Between 1-50 characters
    - Duplicates are automatically removed
    - Maximum 50 total tags per conversation

    Args:
        conversation_id: Conversation UUID
        request: Tags to add
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        Updated conversation with new tags

    Raises:
        HTTPException: 404 if not found, 403 if user doesn't own it, 400 if tags invalid
    """
    try:
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Verify ownership
        if conversation.user_id != current_user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify another user's conversation"
            )

        # Add tags
        from quration.repositories.base import RepositoryError

        updated = await repo.add_tags(conversation_id, request.tags)
        await session.commit()

        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Failed to update conversation"
            )

        return ConversationResponse(
            id=str(updated.id),
            user_id=str(updated.user_id),
            title=updated.title,
            tags=updated.tags,
            created_at=updated.created_at.isoformat(),
            updated_at=updated.updated_at.isoformat(),
            metadata=updated.metadata
        )

    except HTTPException:
        raise
    except RepositoryError as e:
        logger.error(f"Repository error adding tags: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to add tags to conversation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/conversations/{conversation_id}/tags/{tag}",
    response_model=ConversationResponse,
    summary="Remove tag from conversation",
    description="Remove a specific tag from a conversation"
)
async def remove_conversation_tag(
    conversation_id: UUID = Path(..., description="Conversation UUID"),
    tag: str = Path(..., description="Tag to remove"),
    current_user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Remove a tag from a conversation.

    Tag removal is case-insensitive. If the tag doesn't exist, returns
    the conversation unchanged (idempotent operation).

    Args:
        conversation_id: Conversation UUID
        tag: Tag to remove
        current_user_id: Authenticated user UUID
        session: Database session

    Returns:
        Updated conversation

    Raises:
        HTTPException: 404 if not found, 403 if user doesn't own it
    """
    try:
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Verify ownership
        if conversation.user_id != current_user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify another user's conversation"
            )

        # Remove tag
        updated = await repo.remove_tag(conversation_id, tag)
        await session.commit()

        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Failed to update conversation"
            )

        return ConversationResponse(
            id=str(updated.id),
            user_id=str(updated.user_id),
            title=updated.title,
            tags=updated.tags,
            created_at=updated.created_at.isoformat(),
            updated_at=updated.updated_at.isoformat(),
            metadata=updated.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove tag from conversation: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/conversations/search",
    response_model=List[ConversationSearchResponse],
    summary="Search conversations",
    description="Search conversations by text query and/or tags with relevance scoring"
)
async def search_conversations(
    current_user_id: UUID = Depends(get_current_user_id),
    q: str | None = Query(None, description="Text search query (searches title and messages)"),
    tags: str | None = Query(None, description="Comma-separated list of tags to filter by"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    session: AsyncSession = Depends(get_async_session),
):
    """Search conversations by text and/or tags.

    Supports:
    - Text search in conversation titles and message content
    - Tag filtering (AND logic - all tags must match)
    - Combined text + tag search
    - Relevance scoring and ranking
    - Pagination

    Args:
        current_user_id: Authenticated user UUID
        q: Optional text query
        tags: Optional comma-separated tags (e.g., "rna-seq,melanoma")
        limit: Maximum results to return
        offset: Number to skip for pagination
        session: Database session

    Returns:
        List of matching conversations with relevance scores

    Examples:
        - Search by text: ?q=melanoma
        - Search by tags: ?tags=rna-seq,experiment
        - Combined: ?q=melanoma&tags=rna-seq
        - Paginated: ?q=cancer&limit=10&offset=20
    """
    try:
        # Parse tags from comma-separated string
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        repo = ConversationRepository(session)
        results = await repo.search_conversations(
            user_id=current_user_id,
            text_query=q,
            tags=tag_list,
            limit=limit,
            offset=offset
        )

        # Convert to response models
        return [
            ConversationSearchResponse(**result)
            for result in results
        ]

    except Exception as e:
        logger.error(f"Failed to search conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
