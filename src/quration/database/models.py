"""SQLAlchemy ORM models for the Quration context memory database.

This module defines all database tables using SQLAlchemy 2.0 async ORM:
- users: User accounts
- conversations: Chat conversations
- messages: Individual messages in conversations
- searches: Search queries and metadata
- search_results: Individual dataset results from searches
- user_interactions: User actions on datasets
- user_preferences: Learned user preferences
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    UUID,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from quration.database.types import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    type_annotation_map = {
        dict[str, Any]: JSON,
    }


class MetadataDescriptor:
    def __get__(self, instance, owner):
        if instance is None:
            return Base.metadata
        return instance.meta_data

    def __set__(self, instance, value):
        instance.meta_data = value


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    searches: Mapped[list["Search"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["UserInteraction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, external_id={self.external_id})>"


class Conversation(Base):
    """Conversation model for chat sessions."""

    __tablename__ = "conversations"
    __table_args__ = (Index("idx_conversations_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    meta_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    metadata = MetadataDescriptor()

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    searches: Mapped[list["Search"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["UserInteraction"]] = relationship(
        back_populates="conversation"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title={self.title})>"


class Message(Base):
    """Message model for individual chat messages."""

    __tablename__ = "messages"
    __table_args__ = (Index("idx_messages_conversation", "conversation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    meta_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    metadata = MetadataDescriptor()

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"<Message(id={self.id}, role={self.role}, content={content_preview})>"


class Search(Base):
    """Search query model."""

    __tablename__ = "searches"
    __table_args__ = (
        Index("idx_searches_conversation", "conversation_id"),
        Index("idx_searches_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    query_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    # Client-side default gives microsecond resolution so searches created in quick
    # succession order deterministically (server_default=now() is only second-resolution
    # on SQLite). server_default kept as a DB-level fallback.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="searches")
    user: Mapped["User"] = relationship(back_populates="searches")
    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["UserInteraction"]] = relationship(back_populates="search")

    def __repr__(self) -> str:
        return f"<Search(id={self.id}, result_count={self.result_count})>"


class SearchResult(Base):
    """Individual search result (dataset) model."""

    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("searches.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    meta_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    metadata = MetadataDescriptor()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    search: Mapped["Search"] = relationship(back_populates="results")

    def __repr__(self) -> str:
        return f"<SearchResult(id={self.id}, dataset_id={self.dataset_id}, rank={self.rank})>"


class UserInteraction(Base):
    """User interaction with datasets model."""

    __tablename__ = "user_interactions"
    __table_args__ = (
        Index("idx_interactions_user", "user_id"),
        Index("idx_interactions_dataset", "dataset_id"),
        Index("idx_interactions_user_created", "user_id", "created_at"),  # For cross-conversation recall queries
        Index("idx_interactions_dataset_user", "dataset_id", "user_id"),  # For dataset conversation queries
        Index("idx_interactions_conversation", "conversation_id"),  # For conversation-specific queries
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id")
    )
    search_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    meta_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    metadata = MetadataDescriptor()

    # Relationships
    user: Mapped["User"] = relationship(back_populates="interactions")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="interactions")
    search: Mapped["Search | None"] = relationship(back_populates="interactions")

    def __repr__(self) -> str:
        return f"<UserInteraction(id={self.id}, type={self.interaction_type}, dataset={self.dataset_id})>"


class UserPreference(Base):
    """User preference model for learned preferences."""

    __tablename__ = "user_preferences"
    __table_args__ = (Index("idx_preferences_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    preference_type: Mapped[str] = mapped_column(String(100), nullable=False)
    preference_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<UserPreference(id={self.id}, type={self.preference_type}, confidence={self.confidence_score})>"
