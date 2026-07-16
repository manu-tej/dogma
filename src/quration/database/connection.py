"""Database connection and session management for Quration.

This module provides database connectivity with connection pooling,
session management, and automatic connection handling.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()


class DatabaseConnection:
    """Manages database connections and sessions with pooling."""

    def __init__(self, database_url: str, **engine_kwargs):
        """Initialize database connection.

        Args:
            database_url: PostgreSQL connection URL
            **engine_kwargs: Additional engine configuration options
        """
        self.database_url = database_url
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._engine_kwargs = engine_kwargs

    def initialize(self) -> None:
        """Initialize database engine and session factory."""
        if self._engine is not None:
            logger.warning("Database already initialized")
            return

        # Default connection pool settings
        pool_settings = {
            "poolclass": pool.QueuePool,
            "pool_size": 5,  # Number of connections to maintain
            "max_overflow": 10,  # Additional connections when pool is full
            "pool_timeout": 30,  # Seconds to wait for connection
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "pool_pre_ping": True,  # Test connections before using
            "echo": False,  # Set to True for SQL debugging
        }

        # Override with custom settings
        pool_settings.update(self._engine_kwargs)

        # Create engine with connection pooling
        self._engine = create_engine(self.database_url, **pool_settings)

        # Add event listeners for connection management
        @event.listens_for(self._engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Configure connection on creation."""
            # Set timezone to UTC
            cursor = dbapi_conn.cursor()
            cursor.execute("SET timezone='UTC'")
            cursor.close()
            logger.debug("Database connection established")

        @event.listens_for(self._engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Log connection checkout from pool."""
            logger.debug("Connection checked out from pool")

        # Create session factory
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        logger.info("Database connection initialized successfully")

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy Session instance

        Raises:
            RuntimeError: If database not initialized
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around operations.

        Automatically commits on success and rolls back on error.

        Yields:
            SQLAlchemy Session

        Example:
            >>> db = DatabaseConnection(database_url)
            >>> db.initialize()
            >>> with db.session_scope() as session:
            ...     user = User(email="test@example.com")
            ...     session.add(user)
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database connection and dispose of connection pool."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection closed")

    @property
    def engine(self) -> Engine:
        """Get SQLAlchemy engine.

        Returns:
            SQLAlchemy Engine instance

        Raises:
            RuntimeError: If database not initialized
        """
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._engine

    def create_all_tables(self) -> None:
        """Create all tables in the database.

        Note: In production, use Alembic migrations instead.
        """
        Base.metadata.create_all(self._engine)
        logger.info("All tables created")

    def drop_all_tables(self) -> None:
        """Drop all tables in the database.

        Warning: This will delete all data!
        """
        Base.metadata.drop_all(self._engine)
        logger.warning("All tables dropped")


# Global database instance
_db_instance: DatabaseConnection | None = None


def init_db(database_url: str, **engine_kwargs) -> DatabaseConnection:
    """Initialize global database connection.

    Args:
        database_url: PostgreSQL connection URL
        **engine_kwargs: Additional engine configuration

    Returns:
        DatabaseConnection instance
    """
    global _db_instance

    if _db_instance is not None:
        logger.warning("Database already initialized, returning existing instance")
        return _db_instance

    _db_instance = DatabaseConnection(database_url, **engine_kwargs)
    _db_instance.initialize()

    return _db_instance


def get_db_session() -> Session:
    """Get database session from global instance.

    Returns:
        SQLAlchemy Session

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_instance is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() first or provide DATABASE_URL."
        )

    return _db_instance.get_session()


@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Yields:
        SQLAlchemy Session

    Example:
        >>> from quration.database import db_session_scope
        >>> with db_session_scope() as session:
        ...     users = session.query(User).all()
    """
    if _db_instance is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() first or provide DATABASE_URL."
        )

    with _db_instance.session_scope() as session:
        yield session
