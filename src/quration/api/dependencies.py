"""FastAPI dependencies for database, cache, and authentication.

This module provides dependency injection for:
- Async database sessions
- Redis cache instances
- User authentication
- Service layer initialization
"""

import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from quration.cache.redis_client import RedisClient
from quration.config import get_config
from quration.services.context_service import ContextService

logger = logging.getLogger(__name__)

# Global async engine instance
_async_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[sessionmaker] = None
_redis_cache: Optional[RedisClient] = None


def init_async_db(database_url: str) -> AsyncEngine:
    """Initialize async database engine.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        AsyncEngine instance
    """
    global _async_engine, _async_session_maker

    if _async_engine is not None:
        logger.warning("Async database already initialized")
        return _async_engine

    # Convert postgresql:// to postgresql+asyncpg://
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Create async engine
    # Note: NullPool doesn't support pool_size/max_overflow parameters
    _async_engine = create_async_engine(
        database_url,
        echo=False,
        poolclass=NullPool,  # Use NullPool for better async behavior
    )

    # Create session maker
    _async_session_maker = sessionmaker(
        _async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Async database engine initialized")
    return _async_engine


def init_redis_cache() -> Optional[RedisClient]:
    """Initialize Redis cache instance.

    Returns:
        RedisClient instance or None if disabled
    """
    global _redis_cache

    if _redis_cache is not None:
        return _redis_cache

    config = get_config()
    if config.redis.enabled:
        _redis_cache = RedisClient(config.redis)
        logger.info("Redis cache initialized")
    else:
        logger.info("Redis cache disabled")

    return _redis_cache


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session.

    Yields:
        AsyncSession instance

    Raises:
        HTTPException: If database not initialized
    """
    if _async_session_maker is None:
        raise HTTPException(
            status_code=500,
            detail="Database not initialized. Call init_async_db() on startup."
        )

    async with _async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def get_redis_cache() -> Optional[RedisClient]:
    """Dependency for getting Redis cache instance.

    Returns:
        RedisClient instance or None if disabled
    """
    return _redis_cache


async def get_context_service(
    session: AsyncSession = Depends(get_async_session),
    cache: Optional[RedisClient] = Depends(get_redis_cache),
) -> ContextService:
    """Dependency for getting ContextService instance.

    Args:
        session: Async database session
        cache: Optional Redis cache

    Returns:
        ContextService instance
    """
    return ContextService(session, cache)


async def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> UUID:
    """Dependency for getting current user ID from header.

    This is a simple implementation. In production, you would:
    1. Validate JWT tokens
    2. Extract user ID from authenticated session
    3. Use proper authentication middleware

    Args:
        x_user_id: User ID from X-User-Id header

    Returns:
        User UUID

    Raises:
        HTTPException: If user ID not provided or invalid
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="User authentication required. Provide X-User-Id header."
        )

    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {x_user_id}"
        )


async def get_optional_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> Optional[UUID]:
    """Dependency for getting optional user ID from header.

    Args:
        x_user_id: User ID from X-User-Id header

    Returns:
        User UUID or None if not provided
    """
    if not x_user_id:
        return None

    try:
        return UUID(x_user_id)
    except ValueError:
        return None
