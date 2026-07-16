"""Cache services for different data types.

This module provides specialized cache services for:
- Conversation contexts (24h TTL)
- User preferences (7d TTL)
- Search results (1h TTL)
- Session tokens (30d TTL)
"""

from quration.cache.services.conversation_cache import (
    ConversationCache,
    get_conversation_cache,
)
from quration.cache.services.preference_cache import PreferenceCache, get_preference_cache
from quration.cache.services.search_cache import SearchCache, get_search_cache
from quration.cache.services.session_cache import SessionCache, get_session_cache

__all__ = [
    "ConversationCache",
    "get_conversation_cache",
    "PreferenceCache",
    "get_preference_cache",
    "SearchCache",
    "get_search_cache",
    "SessionCache",
    "get_session_cache",
]
