"""Integration tests for search storage.

Tests search and search result persistence:
- save_search_with_results() flow
- get_conversation_searches() retrieval
- Search result pagination
- Query spec storage and retrieval
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from quration.database.models import Conversation, User
from quration.repositories.search import SearchRepository
from quration.services.context_service import ContextService


class TestSearchStorage:
    """Test search storage and retrieval."""

    @pytest.mark.asyncio
    async def test_save_search_basic(
        self,
        async_db_session: AsyncSession,
        search_repo: SearchRepository,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
    ):
        """Test saving a basic search."""
        search = await search_repo.save_search(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            result_count=3,
            execution_time_ms=150,
        )
        await async_db_session.commit()

        assert search.id is not None
        assert search.conversation_id == test_conversation.id
        assert search.user_id == test_user.id
        assert search.query_spec["query"] == "breast cancer RNA-seq"
        assert search.result_count == 3
        assert search.execution_time_ms == 150

    @pytest.mark.asyncio
    async def test_save_search_results(
        self,
        async_db_session: AsyncSession,
        search_repo: SearchRepository,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        sample_search_results: list[dict],
    ):
        """Test saving search results."""
        # Create search
        search = await search_repo.save_search(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            result_count=len(sample_search_results),
        )
        await async_db_session.commit()

        # Save results
        await search_repo.save_search_results(
            search_id=search.id,
            results=sample_search_results,
        )
        await async_db_session.commit()

        # Verify results
        results = await search_repo.get_search_results(search.id)
        assert len(results) == 3
        assert results[0].dataset_id == "GSE123456"
        assert results[0].rank == 0
        assert results[1].dataset_id == "GSE789012"
        assert results[1].rank == 1

    @pytest.mark.asyncio
    async def test_get_conversation_searches(
        self,
        async_db_session: AsyncSession,
        search_repo: SearchRepository,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
    ):
        """Test retrieving all searches for a conversation."""
        # Create multiple searches
        search_ids = []
        for i in range(3):
            query_spec = sample_query_spec.copy()
            query_spec["query"] = f"query {i}"

            search = await search_repo.save_search(
                conversation_id=test_conversation.id,
                user_id=test_user.id,
                query_spec=query_spec,
                result_count=i + 1,
            )
            search_ids.append(search.id)
        await async_db_session.commit()

        # Retrieve all searches
        searches = await search_repo.get_conversation_searches(
            test_conversation.id
        )

        assert len(searches) == 3
        # Should be ordered by created_at desc (most recent first)
        assert searches[0].query_spec["query"] == "query 2"
        assert searches[1].query_spec["query"] == "query 1"
        assert searches[2].query_spec["query"] == "query 0"

    @pytest.mark.asyncio
    async def test_query_spec_storage_retrieval(
        self,
        async_db_session: AsyncSession,
        search_repo: SearchRepository,
        test_user: User,
        test_conversation: Conversation,
    ):
        """Test complex query spec storage and retrieval."""
        complex_query_spec = {
            "query": "melanoma RNA-seq",
            "organism": "Homo sapiens",
            "filters": {
                "library_strategy": "RNA-Seq",
                "sample_count_min": 5,
                "sample_count_max": 100,
                "has_paired_end": True,
                "publication_date": {
                    "start": "2020-01-01",
                    "end": "2024-12-31",
                },
            },
            "sort": "relevance",
            "limit": 20,
            "offset": 0,
        }

        # Save search
        search = await search_repo.save_search(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=complex_query_spec,
            result_count=15,
        )
        await async_db_session.commit()

        # Reload and verify all nested fields
        async_db_session.expunge_all()
        reloaded = await search_repo.get_search(search.id)

        assert reloaded is not None
        spec = reloaded.query_spec
        assert spec["query"] == "melanoma RNA-seq"
        assert spec["filters"]["sample_count_min"] == 5
        assert spec["filters"]["has_paired_end"] is True
        assert spec["filters"]["publication_date"]["start"] == "2020-01-01"

    @pytest.mark.asyncio
    async def test_search_result_pagination(
        self,
        async_db_session: AsyncSession,
        search_repo: SearchRepository,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        large_search_results: list[dict],
    ):
        """Test search result pagination."""
        # Create search with many results
        search = await search_repo.save_search(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            result_count=len(large_search_results),
        )
        await async_db_session.commit()

        # Save results
        await search_repo.save_search_results(
            search_id=search.id,
            results=large_search_results,
        )
        await async_db_session.commit()

        # Get paginated results
        page_1 = await search_repo.get_search_results(search.id, limit=10, offset=0)
        page_2 = await search_repo.get_search_results(search.id, limit=10, offset=10)
        page_5 = await search_repo.get_search_results(search.id, limit=10, offset=40)

        assert len(page_1) == 10
        assert len(page_2) == 10
        assert len(page_5) == 10

        # Verify no overlap
        page_1_ids = {r.dataset_id for r in page_1}
        page_2_ids = {r.dataset_id for r in page_2}
        assert len(page_1_ids & page_2_ids) == 0

        # Verify ordering by rank
        assert page_1[0].rank == 0
        assert page_1[9].rank == 9
        assert page_2[0].rank == 10

    @pytest.mark.asyncio
    async def test_search_cache_integration(
        self,
        async_db_session: AsyncSession,
        search_repo: SearchRepository,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        sample_search_results: list[dict],
        redis_client,
    ):
        """Test search caching behavior."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create and save search with results
        search = await search_repo.save_search(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            result_count=len(sample_search_results),
        )
        await async_db_session.commit()

        await search_repo.save_search_results(
            search_id=search.id,
            results=sample_search_results,
        )
        await async_db_session.commit()

        # First load - should cache
        search1 = await search_repo.get_search(search.id, use_cache=True)
        assert search1 is not None
        assert len(search1.results) == 3

        # Expire session
        async_db_session.expunge_all()

        # Second load - should use cache
        search2 = await search_repo.get_search(search.id, use_cache=True)
        assert search2 is not None
        assert search2.id == search.id


class TestSearchWithContextService:
    """Test search operations via context service."""

    @pytest.mark.asyncio
    async def test_save_search_with_results_flow(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        sample_search_results: list[dict],
    ):
        """Test complete save_search_with_results flow."""
        search = await context_service.save_search_with_results(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            results=sample_search_results,
            execution_time_ms=200,
        )

        assert search.id is not None
        assert search.result_count == 3
        assert search.execution_time_ms == 200

        # Verify results were saved
        results = await context_service.search_repo.get_search_results(search.id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_conversation_context_with_searches(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        sample_search_results: list[dict],
    ):
        """Test conversation context includes searches."""
        # Save search
        await context_service.save_search_with_results(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            results=sample_search_results,
        )

        # Get context
        context = await context_service.get_conversation_context(
            test_conversation.id
        )

        assert len(context["searches"]) == 1
        assert context["searches"][0]["result_count"] == 3
        assert context["searches"][0]["query_spec"]["query"] == "breast cancer RNA-seq"

    @pytest.mark.asyncio
    async def test_restore_conversation_state_with_search_results(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        sample_search_results: list[dict],
    ):
        """Test restored conversation state includes full search results."""
        # Save search with results
        await context_service.save_search_with_results(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            results=sample_search_results,
        )

        # Restore state
        state = await context_service.restore_conversation_state(
            test_conversation.id
        )

        assert len(state["searches"]) == 1
        search = state["searches"][0]
        assert len(search["results"]) == 3

        # Verify result details
        assert search["results"][0]["dataset_id"] == "GSE123456"
        assert search["results"][0]["rank"] == 0
        assert search["results"][1]["dataset_id"] == "GSE789012"

    @pytest.mark.asyncio
    async def test_multiple_searches_in_conversation(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        large_search_results: list[dict],
    ):
        """Test conversation with multiple searches."""
        # Add multiple searches with increasing result counts (1..5); large_search_results
        # has enough items for [:i+1] to actually grow (sample_search_results has only 3).
        for i in range(5):
            query_spec = {
                "query": f"search query {i}",
                "filters": {"index": i},
            }
            await context_service.save_search_with_results(
                conversation_id=test_conversation.id,
                user_id=test_user.id,
                query_spec=query_spec,
                results=large_search_results[:i+1],  # Vary result count
            )

        # Get context
        context = await context_service.get_conversation_context(
            test_conversation.id
        )

        assert len(context["searches"]) == 5
        # Most recent first
        assert context["searches"][0]["query_spec"]["query"] == "search query 4"
        assert context["searches"][0]["result_count"] == 5

    @pytest.mark.asyncio
    async def test_get_dataset_searches(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
    ):
        """Test retrieving searches that returned a specific dataset."""
        # Create searches with specific dataset
        results_with_target = [
            {"dataset_id": "GSE123456", "title": "Test", "score": 0.9},
            {"dataset_id": "GSE999999", "title": "Other", "score": 0.8},
        ]

        results_without_target = [
            {"dataset_id": "GSE777777", "title": "Different", "score": 0.7},
        ]

        # Search 1: contains target dataset
        await context_service.save_search_with_results(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            results=results_with_target,
        )

        # Search 2: does not contain target dataset
        await context_service.save_search_with_results(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec={"query": "different search"},
            results=results_without_target,
        )

        # Get searches for specific dataset
        dataset_searches = await context_service.search_repo.get_dataset_searches(
            dataset_id="GSE123456",
            user_id=test_user.id,
        )

        # Should only return the first search
        assert len(dataset_searches) == 1
        assert dataset_searches[0].query_spec["query"] == "breast cancer RNA-seq"
