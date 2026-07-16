"""Tests for cache services.

These tests verify:
- Conversation cache (24h TTL)
- Preference cache (7d TTL)
- Search cache (1h TTL)
- Session cache (30d TTL)
- Cache patterns (write-through, cache-aside)
- TTL management
- Cache invalidation
"""

import pytest
from unittest.mock import Mock, patch

from quration.cache.services.conversation_cache import (
    ConversationCache,
    get_conversation_cache,
)
from quration.cache.services.preference_cache import PreferenceCache, get_preference_cache
from quration.cache.services.search_cache import SearchCache, get_search_cache
from quration.cache.services.session_cache import SessionCache, get_session_cache
from quration.cache.redis_client import reset_redis_client


def _is_redis_available():
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False



@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache singleton between tests."""
    reset_redis_client()
    yield
    reset_redis_client()


class TestConversationCache:
    """Test conversation cache service."""

    def test_initialization(self):
        """Test conversation cache initialization."""
        cache = ConversationCache()
        assert cache.ttl == 86400  # 24 hours in seconds
        assert cache.key_gen is not None

    def test_cache_key_generation(self):
        """Test conversation cache key generation."""
        cache = ConversationCache()
        key = cache.key_gen.conversation_context("conv-123")
        assert "conv:conv-123:context" in key

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_set_and_get(self):
        """Test setting and getting conversation context."""
        cache = ConversationCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        conversation_id = "test-conv-123"
        context = {
            "messages": ["Hello", "How are you?"],
            "metadata": {"user_id": "user-1"},
        }

        # Set context
        success = cache.set(conversation_id, context)
        assert success is True

        # Get context
        retrieved = cache.get(conversation_id)
        assert retrieved == context

        # Clean up
        cache.delete(conversation_id)

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_delete(self):
        """Test deleting conversation context."""
        cache = ConversationCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        conversation_id = "test-conv-delete"
        context = {"test": "data"}

        cache.set(conversation_id, context)
        assert cache.exists(conversation_id) is True

        cache.delete(conversation_id)
        assert cache.exists(conversation_id) is False

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_extend_ttl(self):
        """Test extending TTL for conversation."""
        cache = ConversationCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        conversation_id = "test-conv-ttl"
        cache.set(conversation_id, {"test": "data"}, ttl=60)

        # Extend TTL
        cache.extend_ttl(conversation_id, ttl=120)

        # Check TTL
        ttl = cache.get_ttl(conversation_id)
        assert 60 < ttl <= 120

        # Clean up
        cache.delete(conversation_id)

    def test_cache_miss_returns_none(self):
        """Test cache miss returns None."""
        cache = ConversationCache()
        result = cache.get("non-existent-conversation")
        assert result is None


class TestPreferenceCache:
    """Test preference cache service."""

    def test_initialization(self):
        """Test preference cache initialization."""
        cache = PreferenceCache()
        assert cache.ttl == 604800  # 7 days in seconds

    def test_cache_key_generation(self):
        """Test preference cache key generation."""
        cache = PreferenceCache()
        key = cache.key_gen.user_preference("user-123")
        assert "user:user-123:prefs" in key

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_set_and_get(self):
        """Test setting and getting user preferences."""
        cache = PreferenceCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        user_id = "test-user-123"
        preferences = {
            "theme": "dark",
            "language": "en",
            "notifications": True,
        }

        # Set preferences
        success = cache.set(user_id, preferences)
        assert success is True

        # Get preferences
        retrieved = cache.get(user_id)
        assert retrieved == preferences

        # Clean up
        cache.delete(user_id)


class TestSearchCache:
    """Test search cache service."""

    def test_initialization(self):
        """Test search cache initialization."""
        cache = SearchCache()
        assert cache.ttl == 3600  # 1 hour in seconds

    def test_search_id_generation(self):
        """Test search ID generation from parameters."""
        cache = SearchCache()

        # Same parameters should generate same ID
        id1 = cache.generate_search_id(query="gene", organism="human", limit=10)
        id2 = cache.generate_search_id(query="gene", organism="human", limit=10)
        assert id1 == id2

        # Different parameters should generate different ID
        id3 = cache.generate_search_id(query="protein", organism="human", limit=10)
        assert id1 != id3

    def test_cache_key_generation(self):
        """Test search cache key generation."""
        cache = SearchCache()
        search_id = "abc123def456"
        key = cache.key_gen.search_result(search_id)
        assert f"search:{search_id}:results" in key

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_set_and_get_by_params(self):
        """Test setting and getting search results by parameters."""
        cache = SearchCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        search_params = {
            "query": "gene expression",
            "organism": "human",
            "limit": 10,
        }
        results = {
            "hits": 42,
            "results": [{"id": "1", "name": "Gene 1"}],
        }

        # Set by params
        success = cache.set_by_params(results, **search_params)
        assert success is True

        # Get by params
        retrieved = cache.get_by_params(**search_params)
        assert retrieved == results

        # Clean up
        search_id = cache.generate_search_id(**search_params)
        cache.delete(search_id)


class TestSessionCache:
    """Test session cache service."""

    def test_initialization(self):
        """Test session cache initialization."""
        cache = SessionCache()
        assert cache.ttl == 2592000  # 30 days in seconds

    def test_cache_key_generation(self):
        """Test session cache key generation."""
        cache = SessionCache()
        token = "abc123xyz789"
        key = cache.key_gen.session_token(token)
        assert f"session:{token}" in key

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_set_and_get(self):
        """Test setting and getting session data."""
        cache = SessionCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        token = "test-session-token-123"
        session_data = {
            "user_id": "user-123",
            "created_at": "2025-11-19T00:00:00Z",
            "ip_address": "192.168.1.1",
        }

        # Set session
        success = cache.set(token, session_data)
        assert success is True

        # Get session
        retrieved = cache.get(token)
        assert retrieved == session_data

        # Clean up
        cache.delete(token)

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_refresh_session(self):
        """Test refreshing session TTL."""
        cache = SessionCache()

        if not cache.redis_client.is_available():
            pytest.skip("Redis not available")

        token = "test-session-refresh"
        session_data = {"user_id": "user-123"}

        # Set with short TTL
        cache.set(token, session_data, ttl=60)

        # Refresh to default TTL
        success = cache.refresh(token)
        assert success is True

        # Check TTL is now longer
        ttl = cache.get_ttl(token)
        assert ttl > 60

        # Clean up
        cache.delete(token)


class TestCacheSingletons:
    """Test cache service singleton patterns."""

    def test_get_conversation_cache_singleton(self):
        """Test get_conversation_cache returns singleton."""
        cache1 = get_conversation_cache()
        cache2 = get_conversation_cache()
        assert cache1 is cache2

    def test_get_preference_cache_singleton(self):
        """Test get_preference_cache returns singleton."""
        cache1 = get_preference_cache()
        cache2 = get_preference_cache()
        assert cache1 is cache2

    def test_get_search_cache_singleton(self):
        """Test get_search_cache returns singleton."""
        cache1 = get_search_cache()
        cache2 = get_search_cache()
        assert cache1 is cache2

    def test_get_session_cache_singleton(self):
        """Test get_session_cache returns singleton."""
        cache1 = get_session_cache()
        cache2 = get_session_cache()
        assert cache1 is cache2


class TestCacheGracefulDegradation:
    """Test graceful degradation when Redis is unavailable."""

    @patch("quration.cache.redis_client.RedisClient.is_available")
    def test_conversation_cache_unavailable(self, mock_available):
        """Test conversation cache when Redis is unavailable."""
        mock_available.return_value = False

        cache = ConversationCache()
        result = cache.get("any-conversation")
        assert result is None

        success = cache.set("any-conversation", {"data": "test"})
        assert success is False

    @patch("quration.cache.redis_client.RedisClient.is_available")
    def test_preference_cache_unavailable(self, mock_available):
        """Test preference cache when Redis is unavailable."""
        mock_available.return_value = False

        cache = PreferenceCache()
        result = cache.get("any-user")
        assert result is None

    @patch("quration.cache.redis_client.RedisClient.is_available")
    def test_search_cache_unavailable(self, mock_available):
        """Test search cache when Redis is unavailable."""
        mock_available.return_value = False

        cache = SearchCache()
        result = cache.get("any-search-id")
        assert result is None

    @patch("quration.cache.redis_client.RedisClient.is_available")
    def test_session_cache_unavailable(self, mock_available):
        """Test session cache when Redis is unavailable."""
        mock_available.return_value = False

        cache = SessionCache()
        result = cache.get("any-token")
        assert result is None
