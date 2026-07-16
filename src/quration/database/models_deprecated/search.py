"""Search and SearchResult models for Context Memory Module."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from quration.database.types import JSONB
from sqlalchemy.orm import relationship

from quration.database.connection import Base

if TYPE_CHECKING:
    from quration.database.models.conversation import Conversation
    from quration.database.models.user import User


class Search(Base):
    """Search model for storing search queries and metadata.

    Each search represents a query executed by the user, with
    metadata about the query parameters and results.
    """

    __tablename__ = "searches"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique search identifier",
    )

    # Foreign keys
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Conversation this search belongs to (optional)",
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who executed this search",
    )

    # Query content
    query_text = Column(
        Text,
        nullable=False,
        comment="Natural language query text",
    )

    query_spec = Column(
        JSONB,
        nullable=True,
        comment="Structured query parameters (organism, disease, etc.)",
    )

    # Results metadata
    results_count = Column(
        Integer,
        nullable=True,
        comment="Number of results returned",
    )

    success = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether search completed successfully",
    )

    # Timestamp
    timestamp = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Search execution timestamp",
    )

    # Additional metadata
    meta_data = Column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional search metadata (execution time, filters, etc.)",
    )

    # Relationships
    user = relationship("User", back_populates="searches")
    conversation = relationship("Conversation", back_populates="searches")

    search_results = relationship(
        "SearchResult",
        back_populates="search",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation of Search."""
        query_preview = (
            self.query_text[:50] + "..." if len(self.query_text) > 50 else self.query_text
        )
        return f"<Search(id={self.id}, query={query_preview}, results={self.results_count})>"

    def to_dict(self, include_results: bool = False) -> dict:
        """Convert search to dictionary.

        Args:
            include_results: Whether to include search results in output

        Returns:
            Dictionary representation of search
        """
        result = {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "user_id": str(self.user_id),
            "query_text": self.query_text,
            "query_spec": self.query_spec or {},
            "results_count": self.results_count,
            "success": self.success,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.meta_data or {},
        }

        if include_results:
            result["results"] = [r.to_dict() for r in self.search_results]

        return result


class SearchResult(Base):
    """SearchResult model for storing individual search results.

    Denormalized search results for performance. Each result
    represents a dataset returned by a search query.
    """

    __tablename__ = "search_results"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique search result identifier",
    )

    # Foreign key
    search_id = Column(
        UUID(as_uuid=True),
        ForeignKey("searches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Search this result belongs to",
    )

    # Dataset identification
    dataset_id = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Dataset identifier (e.g., GSE12345)",
    )

    # Result position
    rank = Column(
        Integer,
        nullable=False,
        comment="Position in search results (0-indexed)",
    )

    # Dataset metadata (denormalized for performance)
    title = Column(
        String(1000),
        nullable=True,
        comment="Dataset title",
    )

    summary = Column(
        Text,
        nullable=True,
        comment="Dataset summary/description",
    )

    organism = Column(
        String(200),
        nullable=True,
        index=True,
        comment="Organism name",
    )

    sample_count = Column(
        Integer,
        nullable=True,
        comment="Number of samples in dataset",
    )

    # Score and relevance
    relevance_score = Column(
        JSONB,
        nullable=True,
        comment="Relevance scoring details",
    )

    # Full dataset details (JSONB for flexibility)
    dataset_details = Column(
        JSONB,
        nullable=True,
        comment="Complete dataset metadata",
    )

    # Relationships
    search = relationship("Search", back_populates="search_results")

    def __repr__(self) -> str:
        """String representation of SearchResult."""
        return f"<SearchResult(id={self.id}, dataset_id={self.dataset_id}, rank={self.rank})>"

    def to_dict(self) -> dict:
        """Convert search result to dictionary.

        Returns:
            Dictionary representation of search result
        """
        return {
            "id": str(self.id),
            "search_id": str(self.search_id),
            "dataset_id": self.dataset_id,
            "rank": self.rank,
            "title": self.title,
            "summary": self.summary,
            "organism": self.organism,
            "sample_count": self.sample_count,
            "relevance_score": self.relevance_score or {},
            "dataset_details": self.dataset_details or {},
        }
