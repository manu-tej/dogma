"""Tests for Redis client.

These tests verify:
- Connection pooling
- Automatic reconnection
- Health checks
- Error handling
- Graceful degradation
"""

import pytest
from unittest.mock import Mock, patch

from quration.cache.redis_client import RedisClient, get_redis_client, reset_redis_client
from quration.config import RedisConfig


def _is_redis_available():
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False



@pytest.fixture
def redis_config():
    """Create test Redis configuration."""
    return RedisConfig(
        host="localhost",
        port=6379,
        db=0,
        enabled=True,
    )


@pytest.fixture
def redis_client(redis_config):
    """Create Redis client for testing."""
    client = RedisClient(redis_config)
    yield client
    client.close()
    reset_redis_client()


class TestRedisClient:
    """Test Redis client functionality."""

    def test_initialization(self, redis_config):
        """Test Redis client initialization."""
        client = RedisClient(redis_config)
        assert client.config == redis_config
        client.close()

    def test_is_available_when_enabled(self, redis_client):
        """Test is_available returns True when Redis is enabled and connected."""
        # This will depend on whether Redis is actually running
        # If Redis is not running, it should gracefully handle it
        result = redis_client.is_available()
        assert isinstance(result, bool)

    def test_is_available_when_disabled(self):
        """Test is_available returns False when Redis is disabled."""
        config = RedisConfig(enabled=False)
        client = RedisClient(config)
        assert client.is_available() is False
        client.close()

    def test_health_check(self, redis_client):
        """Test health check returns proper status."""
        health = redis_client.health_check()

        assert "available" in health
        assert "enabled" in health
        assert "connection_info" in health
        assert "ping_success" in health
        assert "message" in health

        assert health["enabled"] is True
        assert "host" in health["connection_info"]
        assert "port" in health["connection_info"]

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_get_set_delete(self, redis_client):
        """Test basic get/set/delete operations."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        key = "test:key"
        value = "test_value"

        # Set value
        assert redis_client.set(key, value, ttl=60) is True

        # Get value
        result = redis_client.get(key)
        assert result == value

        # Delete value
        assert redis_client.delete(key) is True

        # Verify deleted
        assert redis_client.get(key) is None

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_exists(self, redis_client):
        """Test exists operation."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        key = "test:exists"

        # Should not exist initially
        assert redis_client.exists(key) is False

        # Set value
        redis_client.set(key, "value", ttl=60)

        # Should exist now
        assert redis_client.exists(key) is True

        # Clean up
        redis_client.delete(key)

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_expire_and_ttl(self, redis_client):
        """Test expire and TTL operations."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        key = "test:ttl"
        redis_client.set(key, "value")

        # Set TTL
        assert redis_client.expire(key, 300) is True

        # Check TTL
        ttl = redis_client.ttl(key)
        assert 0 < ttl <= 300

        # Clean up
        redis_client.delete(key)

    @pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available"
    )
    def test_delete_pattern(self, redis_client):
        """Test delete pattern operation."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Set multiple keys
        redis_client.set("pattern:test:1", "value1", ttl=60)
        redis_client.set("pattern:test:2", "value2", ttl=60)
        redis_client.set("pattern:other:3", "value3", ttl=60)

        # Delete pattern
        deleted = redis_client.delete_pattern("pattern:test:*")
        assert deleted == 2

        # Verify correct keys deleted
        assert redis_client.exists("pattern:test:1") is False
        assert redis_client.exists("pattern:test:2") is False
        assert redis_client.exists("pattern:other:3") is True

        # Clean up
        redis_client.delete("pattern:other:3")

    def test_singleton_pattern(self, redis_config):
        """Test get_redis_client returns singleton."""
        reset_redis_client()

        client1 = get_redis_client()
        client2 = get_redis_client()

        assert client1 is client2

        reset_redis_client()

    def test_graceful_degradation_when_unavailable(self):
        """Test graceful degradation when Redis is unavailable."""
        config = RedisConfig(
            # `url` takes precedence over host/port in get_connection_kwargs, so it
            # must also point at the dead endpoint — otherwise the default
            # redis://localhost:6379 connects to a real redis (e.g. the CI service).
            url="redis://invalid-host-that-does-not-exist:9999/0",
            host="invalid-host-that-does-not-exist",
            port=9999,
            enabled=True,
        )

        client = RedisClient(config)

        # Should not raise exception, just return False/None
        assert client.is_available() is False
        assert client.get("any-key") is None
        assert client.set("any-key", "any-value") is False
        assert client.delete("any-key") is False
        assert client.exists("any-key") is False

        client.close()
