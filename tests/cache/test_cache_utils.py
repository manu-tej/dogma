"""Tests for cache utilities.

These tests verify:
- Cache key generation
- Serialization/deserialization
- Cache statistics
- Cache-aside decorator
"""

import pytest
from unittest.mock import Mock, patch

from quration.cache.utils import (
    CacheKeyGenerator,
    CacheSerializer,
    CacheStats,
    get_cache_stats,
    cache_aside,
    invalidate_cache_pattern,
)
from pydantic import BaseModel


def _is_redis_available():
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False



class TestCacheKeyGenerator:
    """Test cache key generator."""

    def test_initialization(self):
        """Test key generator initialization."""
        gen = CacheKeyGenerator(prefix="test:")
        assert gen.prefix == "test:"

    def test_conversation_context_key(self):
        """Test conversation context key generation."""
        gen = CacheKeyGenerator(prefix="quration:")
        key = gen.conversation_context("conv-123")
        assert key == "quration:conv:conv-123:context"

    def test_user_preference_key(self):
        """Test user preference key generation."""
        gen = CacheKeyGenerator(prefix="quration:")
        key = gen.user_preference("user-456")
        assert key == "quration:user:user-456:prefs"

    def test_search_result_key(self):
        """Test search result key generation."""
        gen = CacheKeyGenerator(prefix="quration:")
        key = gen.search_result("search-789")
        assert key == "quration:search:search-789:results"

    def test_session_token_key(self):
        """Test session token key generation."""
        gen = CacheKeyGenerator(prefix="quration:")
        key = gen.session_token("token-xyz")
        assert key == "quration:session:token-xyz"

    def test_hash_params(self):
        """Test parameter hashing for consistent keys."""
        # Same params should generate same hash
        hash1 = CacheKeyGenerator.hash_params(query="gene", organism="human", limit=10)
        hash2 = CacheKeyGenerator.hash_params(query="gene", organism="human", limit=10)
        assert hash1 == hash2

        # Different params should generate different hash
        hash3 = CacheKeyGenerator.hash_params(query="protein", organism="human", limit=10)
        assert hash1 != hash3

        # Order shouldn't matter (sorted internally)
        hash4 = CacheKeyGenerator.hash_params(limit=10, organism="human", query="gene")
        assert hash1 == hash4


class TestCacheSerializer:
    """Test cache serializer."""

    def test_serialize_dict(self):
        """Test serializing dictionary."""
        data = {"key": "value", "number": 42}
        serialized = CacheSerializer.serialize(data)
        assert isinstance(serialized, str)
        assert "key" in serialized
        assert "value" in serialized

    def test_serialize_list(self):
        """Test serializing list."""
        data = [1, 2, 3, "four"]
        serialized = CacheSerializer.serialize(data)
        assert isinstance(serialized, str)
        assert "1" in serialized

    def test_serialize_primitives(self):
        """Test serializing primitive types."""
        assert CacheSerializer.serialize("test") == '"test"'
        assert CacheSerializer.serialize(42) == "42"
        assert CacheSerializer.serialize(3.14) == "3.14"
        assert CacheSerializer.serialize(True) == "true"
        assert CacheSerializer.serialize(None) == "null"

    def test_serialize_pydantic_model(self):
        """Test serializing Pydantic model."""
        class TestModel(BaseModel):
            name: str
            age: int

        model = TestModel(name="Alice", age=30)
        serialized = CacheSerializer.serialize(model)
        assert isinstance(serialized, str)
        assert "Alice" in serialized
        assert "30" in serialized

    def test_deserialize_dict(self):
        """Test deserializing to dictionary."""
        data = '{"key": "value", "number": 42}'
        result = CacheSerializer.deserialize(data)
        assert result == {"key": "value", "number": 42}

    def test_deserialize_list(self):
        """Test deserializing to list."""
        data = '[1, 2, 3, "four"]'
        result = CacheSerializer.deserialize(data)
        assert result == [1, 2, 3, "four"]

    def test_deserialize_to_pydantic_model(self):
        """Test deserializing to Pydantic model."""
        class TestModel(BaseModel):
            name: str
            age: int

        data = '{"name": "Alice", "age": 30}'
        result = CacheSerializer.deserialize(data, model_class=TestModel)
        assert isinstance(result, TestModel)
        assert result.name == "Alice"
        assert result.age == 30

    def test_serialize_deserialize_roundtrip(self):
        """Test serialization roundtrip."""
        original = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        serialized = CacheSerializer.serialize(original)
        deserialized = CacheSerializer.deserialize(serialized)

        assert deserialized == original


class TestCacheStats:
    """Test cache statistics."""

    def test_initialization(self):
        """Test stats initialization."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0
        assert stats.total_requests == 0

    def test_record_hit(self):
        """Test recording cache hit."""
        stats = CacheStats()
        stats.record_hit()
        assert stats.hits == 1
        assert stats.total_requests == 1

    def test_record_miss(self):
        """Test recording cache miss."""
        stats = CacheStats()
        stats.record_miss()
        assert stats.misses == 1
        assert stats.total_requests == 1

    def test_record_error(self):
        """Test recording cache error."""
        stats = CacheStats()
        stats.record_error()
        assert stats.errors == 1
        assert stats.total_requests == 1

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()

        assert stats.hit_rate == pytest.approx(66.67, rel=0.01)

    def test_miss_rate_calculation(self):
        """Test miss rate calculation."""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        stats.record_miss()

        assert stats.miss_rate == pytest.approx(66.67, rel=0.01)

    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        stats = CacheStats()
        stats.record_hit()
        stats.record_error()

        assert stats.error_rate == pytest.approx(50.0, rel=0.01)

    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()

        result = stats.to_dict()

        assert "hits" in result
        assert "misses" in result
        assert "errors" in result
        assert "total_requests" in result
        assert "hit_rate" in result
        assert "miss_rate" in result
        assert "error_rate" in result
        assert "uptime_seconds" in result

    def test_reset(self):
        """Test resetting statistics."""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        stats.record_error()

        stats.reset()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0
        assert stats.total_requests == 0

    def test_uptime_seconds(self):
        """Test uptime calculation."""
        import time

        stats = CacheStats()
        time.sleep(0.1)  # Wait 100ms

        uptime = stats.uptime_seconds()
        assert uptime > 0.09  # Should be at least 90ms


class TestCacheAsideDecorator:
    """Test cache-aside decorator."""

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_cache_aside_pattern(self):
        """Test cache-aside decorator pattern."""
        from quration.cache.redis_client import get_redis_client

        redis_client = get_redis_client()
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        call_count = 0

        @cache_aside(
            key_generator=lambda x: f"test:cache_aside:{x}",
            ttl=60,
        )
        def expensive_function(param):
            nonlocal call_count
            call_count += 1
            return {"result": f"computed-{param}"}

        # First call - should call function
        result1 = expensive_function("test1")
        assert result1 == {"result": "computed-test1"}
        assert call_count == 1

        # Second call - should use cache
        result2 = expensive_function("test1")
        assert result2 == {"result": "computed-test1"}
        assert call_count == 1  # Should not increment

        # Different param - should call function again
        result3 = expensive_function("test2")
        assert result3 == {"result": "computed-test2"}
        assert call_count == 2

        # Clean up
        redis_client.delete("test:cache_aside:test1")
        redis_client.delete("test:cache_aside:test2")


class TestCacheInvalidation:
    """Test cache invalidation utilities."""

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_invalidate_cache_pattern(self):
        """Test invalidating cache by pattern."""
        from quration.cache.redis_client import get_redis_client

        redis_client = get_redis_client()
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Set some test keys
        redis_client.set("test:invalidate:1", "value1", ttl=60)
        redis_client.set("test:invalidate:2", "value2", ttl=60)
        redis_client.set("test:keep:3", "value3", ttl=60)

        # Invalidate pattern
        deleted = invalidate_cache_pattern("test:invalidate:*")
        assert deleted == 2

        # Verify correct keys deleted
        assert redis_client.exists("test:invalidate:1") is False
        assert redis_client.exists("test:invalidate:2") is False
        assert redis_client.exists("test:keep:3") is True

        # Clean up
        redis_client.delete("test:keep:3")


class TestCacheStatsGlobal:
    """Test global cache statistics."""

    def test_get_cache_stats_singleton(self):
        """Test get_cache_stats returns singleton."""
        stats1 = get_cache_stats()
        stats2 = get_cache_stats()
        assert stats1 is stats2
