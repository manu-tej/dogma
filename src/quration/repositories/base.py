"""Base repository with common CRUD operations.

This module provides a base repository class with generic CRUD operations
that can be extended by specific repository implementations.
"""

import logging
from typing import Any, Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from quration.cache.redis_client import RedisClient
from quration.utils.resilience import is_retryable_error, retry_on_failure

logger = logging.getLogger(__name__)

# Type variable for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class RepositoryError(Exception):
    """Base exception for repository errors."""

    pass


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations.

    This repository provides generic database operations with
    automatic caching integration.

    Type Parameters:
        ModelType: SQLAlchemy model class
    """

    def __init__(
        self,
        model: type[ModelType],
        session: AsyncSession,
        cache: RedisClient | None = None,
    ):
        """Initialize base repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
            cache: Optional Redis cache instance
        """
        self.model = model
        self.session = session
        self.cache = cache

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created model instance

        Raises:
            RepositoryError: If creation fails
        """
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            await self.session.flush()
            await self.session.refresh(instance)

            logger.debug(f"Created {self.model.__name__} with ID: {instance.id}")
            return instance
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise RepositoryError(f"Failed to create {self.model.__name__}") from e

    @retry_on_failure(
        max_attempts=3,
        min_wait=1.0,
        max_wait=5.0,
        exceptions=(OperationalError, SQLTimeoutError, ConnectionError),
        reraise=False,
    )
    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get a record by ID with retry logic.

        Automatically retries on connection errors and timeouts.

        Args:
            id: Record UUID

        Returns:
            Model instance or None if not found
        """
        try:
            result = await self.session.execute(
                select(self.model).where(self.model.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            # Only log non-retryable errors
            if not is_retryable_error(e):
                logger.error(f"Error getting {self.model.__name__} by ID {id}: {e}")
            return None

    @retry_on_failure(
        max_attempts=3,
        min_wait=1.0,
        max_wait=5.0,
        exceptions=(OperationalError, SQLTimeoutError, ConnectionError),
        reraise=False,
    )
    async def get_all(
        self, limit: int | None = None, offset: int = 0
    ) -> Sequence[ModelType]:
        """Get all records with optional pagination.

        Automatically retries on connection errors and timeouts.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        try:
            query = select(self.model).offset(offset)

            if limit is not None:
                query = query.limit(limit)

            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            if not is_retryable_error(e):
                logger.error(f"Error getting all {self.model.__name__}: {e}")
            return []

    async def update(self, id: UUID, **kwargs: Any) -> ModelType | None:
        """Update a record by ID.

        Args:
            id: Record UUID
            **kwargs: Fields to update

        Returns:
            Updated model instance or None if not found
        """
        try:
            # Get the record first
            instance = await self.get_by_id(id)
            if instance is None:
                return None

            # Update fields
            for key, value in kwargs.items():
                setattr(instance, key, value)

            await self.session.flush()
            await self.session.refresh(instance)

            logger.debug(f"Updated {self.model.__name__} with ID: {id}")
            return instance
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            raise RepositoryError(f"Failed to update {self.model.__name__}") from e

    async def update_many(self, filter_dict: dict[str, Any], **kwargs: Any) -> int:
        """Update multiple records matching filter.

        Args:
            filter_dict: Filter criteria (field: value pairs)
            **kwargs: Fields to update

        Returns:
            Number of records updated
        """
        try:
            stmt = update(self.model)

            # Apply filters
            for key, value in filter_dict.items():
                stmt = stmt.where(getattr(self.model, key) == value)

            # Set values
            stmt = stmt.values(**kwargs)

            result = await self.session.execute(stmt)
            await self.session.flush()

            updated_count = result.rowcount or 0
            logger.debug(f"Updated {updated_count} {self.model.__name__} records")
            return updated_count
        except Exception as e:
            logger.error(f"Error bulk updating {self.model.__name__}: {e}")
            raise RepositoryError(f"Failed to bulk update {self.model.__name__}") from e

    async def delete(self, id: UUID) -> bool:
        """Delete a record by ID.

        Args:
            id: Record UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            result = await self.session.execute(
                delete(self.model).where(self.model.id == id)
            )
            await self.session.flush()

            deleted = (result.rowcount or 0) > 0
            if deleted:
                logger.debug(f"Deleted {self.model.__name__} with ID: {id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__} {id}: {e}")
            raise RepositoryError(f"Failed to delete {self.model.__name__}") from e

    async def delete_many(self, filter_dict: dict[str, Any]) -> int:
        """Delete multiple records matching filter.

        Args:
            filter_dict: Filter criteria (field: value pairs)

        Returns:
            Number of records deleted
        """
        try:
            stmt = delete(self.model)

            # Apply filters
            for key, value in filter_dict.items():
                stmt = stmt.where(getattr(self.model, key) == value)

            result = await self.session.execute(stmt)
            await self.session.flush()

            deleted_count = result.rowcount or 0
            logger.debug(f"Deleted {deleted_count} {self.model.__name__} records")
            return deleted_count
        except Exception as e:
            logger.error(f"Error bulk deleting {self.model.__name__}: {e}")
            raise RepositoryError(f"Failed to bulk delete {self.model.__name__}") from e

    async def count(self, filter_dict: dict[str, Any] | None = None) -> int:
        """Count records matching optional filter.

        Args:
            filter_dict: Optional filter criteria (field: value pairs)

        Returns:
            Number of matching records
        """
        try:
            stmt = select(func.count()).select_from(self.model)

            if filter_dict:
                for key, value in filter_dict.items():
                    stmt = stmt.where(getattr(self.model, key) == value)

            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            return 0

    async def exists(self, filter_dict: dict[str, Any]) -> bool:
        """Check if record exists matching filter.

        Args:
            filter_dict: Filter criteria (field: value pairs)

        Returns:
            True if exists, False otherwise
        """
        count = await self.count(filter_dict)
        return count > 0

    @retry_on_failure(
        max_attempts=3,
        min_wait=1.0,
        max_wait=5.0,
        exceptions=(OperationalError, SQLTimeoutError, ConnectionError),
        reraise=False,
    )
    async def find_one(self, filter_dict: dict[str, Any]) -> ModelType | None:
        """Find a single record matching filter.

        Automatically retries on connection errors and timeouts.

        Args:
            filter_dict: Filter criteria (field: value pairs)

        Returns:
            Model instance or None if not found
        """
        try:
            stmt = select(self.model)

            for key, value in filter_dict.items():
                stmt = stmt.where(getattr(self.model, key) == value)

            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            if not is_retryable_error(e):
                logger.error(f"Error finding {self.model.__name__}: {e}")
            return None

    @retry_on_failure(
        max_attempts=3,
        min_wait=1.0,
        max_wait=5.0,
        exceptions=(OperationalError, SQLTimeoutError, ConnectionError),
        reraise=False,
    )
    async def find_many(
        self,
        filter_dict: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order_by: str | None = None,
        desc: bool = False,
    ) -> Sequence[ModelType]:
        """Find multiple records matching filter with optional ordering.

        Automatically retries on connection errors and timeouts.

        Args:
            filter_dict: Optional filter criteria (field: value pairs)
            limit: Maximum number of records to return
            offset: Number of records to skip
            order_by: Field name to order by
            desc: If True, order descending

        Returns:
            List of model instances
        """
        try:
            stmt = select(self.model)

            # Apply filters
            if filter_dict:
                for key, value in filter_dict.items():
                    stmt = stmt.where(getattr(self.model, key) == value)

            # Apply ordering
            if order_by:
                order_field = getattr(self.model, order_by)
                stmt = stmt.order_by(order_field.desc() if desc else order_field)

            # Apply pagination
            stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            if not is_retryable_error(e):
                logger.error(f"Error finding {self.model.__name__} records: {e}")
            return []

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.session.rollback()

    async def flush(self) -> None:
        """Flush pending changes to the database."""
        await self.session.flush()
