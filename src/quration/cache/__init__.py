"""Redis cache infrastructure for Quration Context Memory Module.

This package provides a comprehensive caching layer with:
- Redis client with connection pooling
- Four specialized cache services (conversation, preference, search, session)
- Automatic TTL management
- Write-through and cache-aside patterns
- Graceful degradation when Redis is unavailable
- Zero data loss guarantee

Quick Start:
    >>> from quration.cache import get_conversation_cache, get_redis_client
    >>>
    >>> # Check Redis health
    >>> redis_client = get_redis_client()
    >>> health = redis_client.health_check()
    >>> print(health)
    >>>
    >>> # Use conversation cache
    >>> cache = get_conversation_cache()
    >>> cache.set("conv-123", {"messages": [...], "context": {...}})
    >>> data = cache.get("conv-123")

Cache Types:
    - ConversationCache: Hot conversation contexts (24h TTL)
    - PreferenceCache: User preferences (7d TTL)
    - SearchCache: Search results (1h TTL)
    - SessionCache: Session tokens (30d TTL)

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_DB: Redis database number (default: 0)
    REDIS_ENABLED: Enable/disable Redis cache (default: True)

Example:
    # Setup local Redis with Docker:
    docker run -d -p 6379:6379 redis:7-alpine

    # In your .env file:
    REDIS_URL=redis://localhost:6379/0
    REDIS_ENABLED=True
"""

try:
    from quration.cache.redis_client import RedisClient, get_redis_client, reset_redis_client
    from quration.cache.utils import (
        CacheKeyGenerator,
        CacheSerializer,
        CacheStats,
        get_cache_stats,
        cache_aside,
        invalidate_cache_pattern,
    )
    from quration.cache.services.conversation_cache import (
        ConversationCache,
        get_conversation_cache,
    )
    from quration.cache.services.preference_cache import PreferenceCache, get_preference_cache
    from quration.cache.services.search_cache import SearchCache, get_search_cache
    from quration.cache.services.session_cache import SessionCache, get_session_cache
except ImportError:
    # redis package not installed — cache module degrades gracefully
    RedisClient = None
    get_redis_client = None
    reset_redis_client = None
    CacheKeyGenerator = None
    CacheSerializer = None
    CacheStats = None
    get_cache_stats = None
    cache_aside = None
    invalidate_cache_pattern = None
    ConversationCache = None
    get_conversation_cache = None
    PreferenceCache = None
    get_preference_cache = None
    SearchCache = None
    get_search_cache = None
    SessionCache = None
    get_session_cache = None

__all__ = [
    # Redis client
    "RedisClient",
    "get_redis_client",
    "reset_redis_client",
    # Utilities
    "CacheKeyGenerator",
    "CacheSerializer",
    "CacheStats",
    "get_cache_stats",
    "cache_aside",
    "invalidate_cache_pattern",
    # Cache services
    "ConversationCache",
    "get_conversation_cache",
    "PreferenceCache",
    "get_preference_cache",
    "SearchCache",
    "get_search_cache",
    "SessionCache",
    "get_session_cache",
]
