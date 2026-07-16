"""Conversation and Message models for Context Memory Module."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from quration.database.types import JSONB
from sqlalchemy.orm import relationship

from quration.database.connection import Base

if TYPE_CHECKING:
    from quration.database.models.search import Search
    from quration.database.models.user import User


class Conversation(Base):
    """Conversation model for storing chat sessions.

    Each conversation represents a continuous chat session between
    a user and the assistant. Conversations can span multiple page
    refreshes and contain multiple messages.
    """

    __tablename__ = "conversations"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique conversation identifier",
    )

    # Foreign keys
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this conversation",
    )

    # Conversation metadata
    title = Column(
        String(500),
        nullable=True,
        comment="Conversation title (auto-generated or user-provided)",
    )

    project_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Optional project/research group identifier",
    )

    # Status
    is_archived = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether conversation is archived",
    )

    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Conversation creation timestamp",
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last message timestamp",
    )

    # Metadata (JSONB for flexibility)
    meta_data = Column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Conversation metadata (datasets explored, topics, etc.)",
    )

    # Relationships
    user = relationship("User", back_populates="conversations")

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp",
        lazy="select",
    )

    searches = relationship(
        "Search",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation of Conversation."""
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title={self.title})>"

    def to_dict(self, include_messages: bool = False) -> dict:
        """Convert conversation to dictionary.

        Args:
            include_messages: Whether to include messages in output

        Returns:
            Dictionary representation of conversation
        """
        result = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "project_id": str(self.project_id) if self.project_id else None,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.meta_data or {},
        }

        if include_messages:
            result["messages"] = [msg.to_dict() for msg in self.messages]

        return result


class Message(Base):
    """Message model for storing individual chat messages.

    Each message represents a single user or assistant message
    within a conversation. Messages are stored with embeddings
    for semantic search.
    """

    __tablename__ = "messages"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique message identifier",
    )

    # Foreign keys
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Conversation this message belongs to",
    )

    # Message content
    role = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Message role: 'user' or 'assistant'",
    )

    content = Column(
        Text,
        nullable=False,
        comment="Message text content",
    )

    # Timestamp
    timestamp = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Message creation timestamp",
    )

    # Vector embedding reference
    embedding_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Reference to vector database embedding",
    )

    # Metadata (JSONB for flexibility)
    meta_data = Column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Message metadata (entities, reasoning, etc.)",
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        """String representation of Message."""
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"<Message(id={self.id}, role={self.role}, content={content_preview})>"

    def to_dict(self) -> dict:
        """Convert message to dictionary.

        Returns:
            Dictionary representation of message
        """
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "embedding_id": self.embedding_id,
            "metadata": self.meta_data or {},
        }
