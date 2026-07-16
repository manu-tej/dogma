"""Redis client with connection pooling and automatic reconnection.

This module provides a Redis client wrapper with the following features:
- Connection pooling for better performance
- Automatic reconnection on failure
- Graceful degradation when Redis is unavailable
- Health check functionality
- Comprehensive error handling and logging
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Optional

import redis
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from quration.config import RedisConfig, get_config
from quration.utils.resilience import CircuitBreakerOpenError, get_circuit_breaker

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with connection pooling and error handling.

    This client provides:
    - Connection pooling for efficient resource usage
    - Automatic reconnection on connection failures
    - Graceful fallback when Redis is unavailable
    - Health check capabilities
    - Thread-safe operations

    Attributes:
        config: Redis configuration
        pool: Connection pool for Redis connections
        client: Redis client instance
        _is_available: Cache availability flag
    """

    def __init__(self, config: Optional[RedisConfig] = None):
        """Initialize Redis client.

        Args:
            config: Redis configuration. If None, loads from global config.
        """
        self.config = config or get_config().redis
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self._is_available = False
        self._circuit_breaker = get_circuit_breaker(
            name="redis",
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=2,
        )
        self._last_reconnect_attempt = 0.0
        self._reconnect_backoff = 2.0  # Start with 2 second backoff

        if self.config.enabled:
            self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize Redis connection pool and client.

        This method sets up the connection pool and creates a Redis client.
        If connection fails, it logs the error but doesn't raise to allow
        graceful degradation.
        """
        try:
            # Get connection parameters
            conn_kwargs = self.config.get_connection_kwargs()

            # Create connection pool
            if "url" in conn_kwargs:
                # URL-based connection
                url = conn_kwargs.pop("url")
                self.pool = ConnectionPool.from_url(
                    url,
                    decode_responses=True,
                    **conn_kwargs
                )
            else:
                # Component-based connection
                self.pool = ConnectionPool(
                    decode_responses=True,
                    **conn_kwargs
                )

            # Create Redis client
            self.client = redis.Redis(connection_pool=self.pool)

            # Test connection
            self.client.ping()
            self._is_available = True

            logger.info(
                f"Redis cache initialized successfully "
                f"(host={self.config.host}, port={self.config.port}, db={self.config.db})"
            )

        except (ConnectionError, TimeoutError) as e:
            logger.warning(
                f"Failed to connect to Redis: {e}. "
                "Cache will be disabled, falling back to database."
            )
            self._is_available = False
            self.client = None
            self.pool = None

        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}", exc_info=True)
            self._is_available = False
            self.client = None
            self.pool = None

    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to Redis with exponential backoff.

        Returns:
            True if reconnection successful, False otherwise
        """
        current_time = time.time()

        # Check if enough time has passed since last reconnect attempt
        if current_time - self._last_reconnect_attempt < self._reconnect_backoff:
            return False

        self._last_reconnect_attempt = current_time

        try:
            logger.info("Attempting to reconnect to Redis...")
            self._initialize_connection()

            if self._is_available:
                logger.info("Redis reconnection successful")
                # Reset backoff on success
                self._reconnect_backoff = 2.0
                # Reset circuit breaker
                self._circuit_breaker.reset()
                return True
            else:
                # Increase backoff for next attempt (max 60 seconds)
                self._reconnect_backoff = min(self._reconnect_backoff * 2, 60.0)
                return False

        except Exception as e:
            logger.warning(f"Redis reconnection failed: {e}")
            # Increase backoff for next attempt
            self._reconnect_backoff = min(self._reconnect_backoff * 2, 60.0)
            return False

    def is_available(self) -> bool:
        """Check if Redis cache is available.

        This method includes automatic reconnection logic with circuit breaker.

        Returns:
            True if Redis is available and healthy, False otherwise
        """
        if not self.config.enabled:
            return False

        if not self._is_available or self.client is None:
            # Try to reconnect if circuit breaker allows
            try:
                self._circuit_breaker.call(self._attempt_reconnect)
            except CircuitBreakerOpenError:
                # Circuit breaker is open, don't attempt reconnect
                pass
            except Exception:
                # Reconnection failed, but we've logged it
                pass

            # Return current availability status
            return self._is_available

        try:
            # Quick health check with circuit breaker
            def ping_check() -> bool:
                self.client.ping()
                return True

            result = self._circuit_breaker.call(ping_check)
            return result

        except CircuitBreakerOpenError:
            logger.debug("Redis circuit breaker is open, marking as unavailable")
            self._is_available = False
            return False
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"Redis health check failed: {e}")
            self._is_available = False
            return False

    def health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check on Redis connection.

        Returns:
            Dictionary with health check results including:
            - available: Whether Redis is available
            - enabled: Whether Redis is enabled in config
            - connection_info: Connection details
            - pool_stats: Connection pool statistics (if available)
            - ping_success: Whether ping succeeded
        """
        health = {
            "available": False,
            "enabled": self.config.enabled,
            "connection_info": {
                "host": self.config.host,
                "port": self.config.port,
                "db": self.config.db,
            },
            "pool_stats": None,
            "ping_success": False,
        }

        if not self.config.enabled:
            health["message"] = "Redis cache is disabled in configuration"
            return health

        if self.client is None:
            health["message"] = "Redis client not initialized"
            return health

        try:
            # Test connection
            self.client.ping()
            health["ping_success"] = True
            health["available"] = True

            # Get pool statistics if available
            if self.pool:
                health["pool_stats"] = {
                    "max_connections": self.pool.max_connections,
                    "connection_kwargs": {
                        k: v for k, v in self.pool.connection_kwargs.items()
                        if k not in ["password"]  # Don't expose password
                    }
                }

            health["message"] = "Redis is healthy and available"

        except (ConnectionError, TimeoutError) as e:
            health["message"] = f"Connection failed: {e}"
        except RedisError as e:
            health["message"] = f"Redis error: {e}"
        except Exception as e:
            health["message"] = f"Unexpected error: {e}"

        return health

    @contextmanager
    def pipeline(self):
        """Context manager for Redis pipeline operations.

        Yields:
            Redis pipeline object for batched operations

        Example:
            with client.pipeline() as pipe:
                pipe.set("key1", "value1")
                pipe.set("key2", "value2")
                pipe.execute()
        """
        if not self.is_available():
            raise RuntimeError("Redis is not available")

        pipe = self.client.pipeline()
        try:
            yield pipe
        finally:
            pipe.reset()

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        if not self.is_available():
            return None

        try:
            return self.client.get(key)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis get failed for key '{key}': {e}")
            self._is_available = False
            return None
        except RedisError as e:
            logger.error(f"Redis error during get for key '{key}': {e}")
            return None

    def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in Redis cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            if ttl:
                return bool(self.client.setex(key, ttl, value))
            else:
                return bool(self.client.set(key, value))
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis set failed for key '{key}': {e}")
            self._is_available = False
            return False
        except RedisError as e:
            logger.error(f"Redis error during set for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from Redis cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False otherwise
        """
        if not self.is_available():
            return False

        try:
            return bool(self.client.delete(key))
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis delete failed for key '{key}': {e}")
            self._is_available = False
            return False
        except RedisError as e:
            logger.error(f"Redis error during delete for key '{key}': {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        if not self.is_available():
            return False

        try:
            return bool(self.client.exists(key))
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis exists check failed for key '{key}': {e}")
            self._is_available = False
            return False
        except RedisError as e:
            logger.error(f"Redis error during exists check for key '{key}': {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        if not self.is_available():
            return 0

        try:
            keys = list(self.client.scan_iter(match=pattern))
            if keys:
                return self.client.delete(*keys)
            return 0
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis delete_pattern failed for pattern '{pattern}': {e}")
            self._is_available = False
            return 0
        except RedisError as e:
            logger.error(f"Redis error during delete_pattern for '{pattern}': {e}")
            return 0

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for an existing key.

        Args:
            key: Cache key
            ttl: Time to live in seconds

        Returns:
            True if TTL was set, False otherwise
        """
        if not self.is_available():
            return False

        try:
            return bool(self.client.expire(key, ttl))
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis expire failed for key '{key}': {e}")
            self._is_available = False
            return False
        except RedisError as e:
            logger.error(f"Redis error during expire for key '{key}': {e}")
            return False

    def ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        if not self.is_available():
            return -2

        try:
            return self.client.ttl(key)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis ttl check failed for key '{key}': {e}")
            self._is_available = False
            return -2
        except RedisError as e:
            logger.error(f"Redis error during ttl check for key '{key}': {e}")
            return -2

    def flushdb(self) -> bool:
        """Flush all keys in current database.

        Warning: This deletes ALL keys in the current database!

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            self.client.flushdb()
            logger.warning("Redis database flushed - all keys deleted")
            return True
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis flushdb failed: {e}")
            self._is_available = False
            return False
        except RedisError as e:
            logger.error(f"Redis error during flushdb: {e}")
            return False

    def close(self) -> None:
        """Close Redis connection and clean up resources."""
        if self.pool:
            try:
                self.pool.disconnect()
                logger.info("Redis connection pool closed")
            except Exception as e:
                logger.error(f"Error closing Redis pool: {e}")
            finally:
                self.pool = None
                self.client = None
                self._is_available = False


# Singleton instance
_redis_client: Optional[RedisClient] = None


def get_redis_client(config: Optional[RedisConfig] = None) -> RedisClient:
    """Get or create singleton Redis client instance.

    Args:
        config: Optional Redis configuration. If None, uses global config.

    Returns:
        RedisClient instance
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient(config)

    return _redis_client


def reset_redis_client() -> None:
    """Reset singleton Redis client (useful for testing)."""
    global _redis_client

    if _redis_client:
        _redis_client.close()

    _redis_client = None


# Cache key builders
def build_conversation_key(conversation_id: str) -> str:
    """Build cache key for conversation data.

    Args:
        conversation_id: Conversation UUID string

    Returns:
        Cache key string
    """
    return f"conversation:{conversation_id}"


def build_search_results_key(search_id: str) -> str:
    """Build cache key for search results.

    Args:
        search_id: Search UUID string

    Returns:
        Cache key string
    """
    return f"search_results:{search_id}"


def build_user_preferences_key(user_id: str) -> str:
    """Build cache key for user preferences.

    Args:
        user_id: User UUID string

    Returns:
        Cache key string
    """
    return f"user_prefs:{user_id}"


def build_user_interactions_key(user_id: str, dataset_id: str) -> str:
    """Build cache key for user-dataset interactions.

    Args:
        user_id: User UUID string
        dataset_id: Dataset ID string

    Returns:
        Cache key string
    """
    return f"user_interactions:{user_id}:{dataset_id}"
