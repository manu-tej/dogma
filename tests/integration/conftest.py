"""Test fixtures for integration tests.

Provides comprehensive fixtures for database, cache, and test data.
"""

import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from quration.cache.redis_client import RedisClient, reset_redis_client
from quration.database.models import Base, Conversation, Message, User
from quration.repositories.conversation import ConversationRepository
from quration.repositories.interaction import InteractionRepository
from quration.repositories.search import SearchRepository
from quration.repositories.user import UserRepository
from quration.services.context_service import ContextService


# Set up event loop for pytest-asyncio
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database fixtures
@pytest_asyncio.fixture
async def async_engine():
    """Create async SQLite engine for testing.

    Uses in-memory SQLite database for fast, isolated tests.
    """
    # Create in-memory SQLite database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing.

    Provides a clean session for each test with automatic rollback.
    """
    # Create session factory
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


# Cache fixtures
@pytest.fixture(autouse=True)
def reset_cache_singleton():
    """Reset Redis cache singleton between tests."""
    reset_redis_client()
    yield
    reset_redis_client()


@pytest.fixture
def redis_client() -> RedisClient:
    """Get Redis client for testing.

    Will use real Redis if available, gracefully degrades if not.
    """
    client = RedisClient()

    # Clear any existing test data if Redis is available
    if client.is_available():
        # Use a test prefix to avoid polluting production data
        try:
            # Only clear keys with test prefix
            import redis
            r = redis.Redis(
                host=client.config.host,
                port=client.config.port,
                db=client.config.db,
                decode_responses=True,
            )
            test_keys = r.keys("test:*")
            if test_keys:
                r.delete(*test_keys)
        except Exception:
            pass  # Ignore cleanup errors

    return client


# User fixtures
@pytest_asyncio.fixture
async def test_user(async_db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(external_id=f"test-user-{uuid.uuid4()}")
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_2(async_db_session: AsyncSession) -> User:
    """Create a second test user for multi-user tests."""
    user = User(external_id=f"test-user-2-{uuid.uuid4()}")
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


# Conversation fixtures
@pytest_asyncio.fixture
async def test_conversation(
    async_db_session: AsyncSession, test_user: User
) -> Conversation:
    """Create a test conversation with messages."""
    conversation = Conversation(
        user_id=test_user.id,
        title="Test Conversation",
        metadata={"test": True},
    )
    async_db_session.add(conversation)
    await async_db_session.flush()

    # Add some messages
    messages = [
        Message(
            conversation_id=conversation.id,
            role="user",
            content="Hello, I need help with RNA-seq analysis",
            metadata={},
        ),
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content="I can help you with that. What organism are you working with?",
            metadata={},
        ),
        Message(
            conversation_id=conversation.id,
            role="user",
            content="Human breast cancer samples",
            metadata={},
        ),
    ]
    for msg in messages:
        async_db_session.add(msg)

    await async_db_session.commit()
    await async_db_session.refresh(conversation)

    return conversation


@pytest_asyncio.fixture
async def empty_conversation(
    async_db_session: AsyncSession, test_user: User
) -> Conversation:
    """Create an empty conversation without messages."""
    conversation = Conversation(
        user_id=test_user.id,
        title="Empty Conversation",
        metadata={},
    )
    async_db_session.add(conversation)
    await async_db_session.commit()
    await async_db_session.refresh(conversation)
    return conversation


# Repository fixtures
@pytest_asyncio.fixture
async def conversation_repo(
    async_db_session: AsyncSession, redis_client: RedisClient
) -> ConversationRepository:
    """Create conversation repository."""
    return ConversationRepository(async_db_session, redis_client)


@pytest_asyncio.fixture
async def search_repo(
    async_db_session: AsyncSession, redis_client: RedisClient
) -> SearchRepository:
    """Create search repository."""
    return SearchRepository(async_db_session, redis_client)


@pytest_asyncio.fixture
async def user_repo(
    async_db_session: AsyncSession, redis_client: RedisClient
) -> UserRepository:
    """Create user repository."""
    return UserRepository(async_db_session, redis_client)


@pytest_asyncio.fixture
async def interaction_repo(
    async_db_session: AsyncSession, redis_client: RedisClient
) -> InteractionRepository:
    """Create interaction repository."""
    return InteractionRepository(async_db_session, redis_client)


# Service fixtures
@pytest_asyncio.fixture
async def context_service(
    async_db_session: AsyncSession, redis_client: RedisClient
) -> ContextService:
    """Create context service with all repositories."""
    return ContextService(async_db_session, redis_client)


# Sample data fixtures
@pytest.fixture
def sample_search_results() -> list[dict]:
    """Sample search results for testing."""
    return [
        {
            "dataset_id": "GSE123456",
            "title": "RNA-seq analysis of breast cancer",
            "organism": "Homo sapiens",
            "score": 0.95,
        },
        {
            "dataset_id": "GSE789012",
            "title": "Melanoma gene expression study",
            "organism": "Homo sapiens",
            "score": 0.87,
        },
        {
            "dataset_id": "GSE345678",
            "title": "Breast tissue RNA-seq",
            "organism": "Homo sapiens",
            "score": 0.82,
        },
    ]


@pytest.fixture
def sample_query_spec() -> dict:
    """Sample search query specification."""
    return {
        "query": "breast cancer RNA-seq",
        "organism": "Homo sapiens",
        "filters": {
            "library_strategy": "RNA-Seq",
            "sample_count_min": 3,
        },
        "limit": 10,
    }


@pytest.fixture
def sample_preferences() -> list[dict]:
    """Sample user preferences."""
    return [
        {
            "preference_key": "organism",
            "preference_value": "Homo sapiens",
            "confidence": 0.9,
            "evidence": "User searched for human datasets 15 times",
        },
        {
            "preference_key": "library_strategy",
            "preference_value": "RNA-Seq",
            "confidence": 0.85,
            "evidence": "User analyzed 12 RNA-seq datasets",
        },
        {
            "preference_key": "disease",
            "preference_value": "cancer",
            "confidence": 0.75,
            "evidence": "User viewed 8 cancer-related datasets",
        },
    ]


@pytest.fixture
def large_message_list() -> list[dict]:
    """Generate large message list for stress testing."""
    messages = []
    for i in range(100):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}: This is test message content that simulates a real conversation.",
            "metadata": {"index": i},
        })
    return messages


@pytest.fixture
def large_search_results() -> list[dict]:
    """Generate large search results list for stress testing."""
    results = []
    for i in range(50):
        results.append({
            "dataset_id": f"GSE{100000 + i}",
            "title": f"Dataset {i}: Test RNA-seq study",
            "organism": "Homo sapiens",
            "score": 1.0 - (i * 0.01),
        })
    return results
