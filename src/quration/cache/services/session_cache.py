"""Session token caching service.

This service provides caching for session tokens with 30-day TTL.
It implements write-through cache pattern for mutations and cache-aside for reads.

Cache pattern:
- Key: session:{token}
- TTL: 30 days (2592000 seconds)
- Write-through: Updates go to both cache and database
- Cache-aside: Read from cache, fallback to database on miss
"""

import logging
from typing import Any, Optional

from quration.cache.redis_client import get_redis_client
from quration.cache.utils import CacheKeyGenerator, CacheSerializer, get_cache_stats
from quration.config import get_config

logger = logging.getLogger(__name__)


class SessionCache:
    """Cache service for session tokens.

    This service manages caching of session tokens with:
    - 30-day TTL for long-lived sessions
    - Write-through cache pattern
    - Automatic fallback to database
    - Token validation and expiry management

    Attributes:
        key_gen: Cache key generator
        ttl: Time to live in seconds (30 days)
        stats: Cache statistics tracker
    """

    def __init__(self):
        """Initialize session cache service."""
        config = get_config()
        self.key_gen = CacheKeyGenerator(prefix=config.redis.key_prefix)
        self.ttl = config.redis.ttl_session
        self.stats = get_cache_stats()
        self.redis_client = get_redis_client()

    def get(self, token: str) -> Optional[dict[str, Any]]:
        """Get session data from cache.

        Implements cache-aside pattern:
        1. Check cache first
        2. Return cached data if found
        3. Return None on cache miss (caller should fetch from database)

        Args:
            token: Session token

        Returns:
            Session data dictionary if cached, None otherwise
        """
        cache_key = self.key_gen.session_token(token)

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache for session")
            self.stats.record_error()
            return None

        # Try to get from cache
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats.record_hit()
                logger.debug(f"Cache hit for session token")
                return CacheSerializer.deserialize(cached_data)
            else:
                self.stats.record_miss()
                logger.debug(f"Cache miss for session token")
                return None

        except Exception as e:
            logger.error(f"Error reading session cache: {e}", exc_info=True)
            self.stats.record_error()
            return None

    def set(
        self,
        token: str,
        session_data: dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set session data in cache.

        Implements write-through cache pattern:
        - Cache the data with 30-day TTL
        - Caller should also write to database

        Args:
            token: Session token
            session_data: Session data to cache (user_id, metadata, etc.)
            ttl: Optional custom TTL in seconds (defaults to 30 days)

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = self.key_gen.session_token(token)
        cache_ttl = ttl or self.ttl

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache write for session")
            return False

        # Cache the session data
        try:
            serialized = CacheSerializer.serialize(session_data)
            success = self.redis_client.set(cache_key, serialized, ttl=cache_ttl)

            if success:
                logger.debug(
                    f"Cached session with TTL {cache_ttl}s"
                )
            else:
                logger.warning(f"Failed to cache session")

            return success

        except Exception as e:
            logger.error(f"Error writing session cache: {e}", exc_info=True)
            return False

    def delete(self, token: str) -> bool:
        """Delete session from cache.

        Used for logout or session invalidation.

        Args:
            token: Session token

        Returns:
            True if deleted, False otherwise
        """
        cache_key = self.key_gen.session_token(token)

        if not self.redis_client.is_available():
            return False

        try:
            deleted = self.redis_client.delete(cache_key)
            if deleted:
                logger.debug(f"Deleted session cache")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting session cache: {e}", exc_info=True)
            return False

    def exists(self, token: str) -> bool:
        """Check if session exists in cache.

        Quick validation without deserializing session data.

        Args:
            token: Session token

        Returns:
            True if exists in cache, False otherwise
        """
        cache_key = self.key_gen.session_token(token)

        if not self.redis_client.is_available():
            return False

        return self.redis_client.exists(cache_key)

    def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a specific user.

        Note: This requires sessions to be stored with user_id in the key
        or requires fetching all sessions and filtering. For now, this is
        a placeholder that requires implementation based on session structure.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions invalidated
        """
        logger.warning(
            f"invalidate_user_sessions not fully implemented. "
            f"Would need to scan all sessions for user_id: {user_id}"
        )
        # TODO: Implement based on session structure
        # Options:
        # 1. Store separate user -> sessions mapping
        # 2. Scan all sessions and filter by user_id (slow)
        # 3. Use Redis Sets to track user sessions
        return 0

    def invalidate_all(self) -> int:
        """Invalidate all session caches.

        Warning: This deletes ALL session caches (logs out all users)!

        Returns:
            Number of keys deleted
        """
        if not self.redis_client.is_available():
            return 0

        pattern = f"{self.key_gen.prefix}session:*"
        deleted = self.redis_client.delete_pattern(pattern)
        logger.warning(f"Invalidated all session caches ({deleted} keys)")
        return deleted

    def extend_ttl(self, token: str, ttl: Optional[int] = None) -> bool:
        """Extend TTL for a session.

        Useful for "remember me" functionality or extending active sessions.

        Args:
            token: Session token
            ttl: New TTL in seconds (defaults to 30 days)

        Returns:
            True if TTL was extended, False otherwise
        """
        cache_key = self.key_gen.session_token(token)
        cache_ttl = ttl or self.ttl

        if not self.redis_client.is_available():
            return False

        try:
            success = self.redis_client.expire(cache_key, cache_ttl)
            if success:
                logger.debug(f"Extended TTL for session to {cache_ttl}s")
            return success

        except Exception as e:
            logger.error(f"Error extending session cache TTL: {e}", exc_info=True)
            return False

    def get_ttl(self, token: str) -> int:
        """Get remaining TTL for a session.

        Useful for showing "session expires in X minutes" to users.

        Args:
            token: Session token

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        cache_key = self.key_gen.session_token(token)

        if not self.redis_client.is_available():
            return -2

        return self.redis_client.ttl(cache_key)

    def refresh(self, token: str) -> bool:
        """Refresh session by resetting TTL to default.

        Convenience method to extend active sessions.

        Args:
            token: Session token

        Returns:
            True if session was refreshed, False otherwise
        """
        return self.extend_ttl(token, self.ttl)


# Singleton instance
_session_cache: Optional[SessionCache] = None


def get_session_cache() -> SessionCache:
    """Get or create singleton session cache instance.

    Returns:
        SessionCache instance
    """
    global _session_cache

    if _session_cache is None:
        _session_cache = SessionCache()

    return _session_cache
