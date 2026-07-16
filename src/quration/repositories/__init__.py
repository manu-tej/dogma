"""Repository module for data access layer.

This module provides repository classes that handle database operations
with caching integration for the Quration context memory system.
"""

from quration.repositories.base import BaseRepository, RepositoryError
from quration.repositories.conversation import ConversationRepository
from quration.repositories.interaction import InteractionRepository
from quration.repositories.search import SearchRepository
from quration.repositories.user import UserRepository

__all__ = [
    # Base
    "BaseRepository",
    "RepositoryError",
    # Repositories
    "ConversationRepository",
    "SearchRepository",
    "UserRepository",
    "InteractionRepository",
]
