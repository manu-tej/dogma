"""UserInteraction and UserPreference models for Context Memory Module."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from quration.database.types import JSONB
from sqlalchemy.orm import relationship

from quration.database.connection import Base

if TYPE_CHECKING:
    from quration.database.models.user import User


class UserInteraction(Base):
    """UserInteraction model for tracking user actions on datasets.

    Tracks all user interactions with datasets including views,
    analyses, exports, and downloads. Used for preference learning
    and cross-conversation context.
    """

    __tablename__ = "user_interactions"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique interaction identifier",
    )

    # Foreign key
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who performed this interaction",
    )

    # Dataset identification
    dataset_id = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Dataset identifier (e.g., GSE12345)",
    )

    # Interaction type
    interaction_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of interaction: viewed, analyzed, exported, downloaded",
    )

    # Timestamp
    timestamp = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Interaction timestamp",
    )

    # Metadata (JSONB for flexibility)
    meta_data = Column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Interaction metadata (analysis type, filters, etc.)",
    )

    # Relationships
    user = relationship("User", back_populates="interactions")

    def __repr__(self) -> str:
        """String representation of UserInteraction."""
        return (
            f"<UserInteraction(id={self.id}, "
            f"dataset_id={self.dataset_id}, "
            f"type={self.interaction_type})>"
        )

    def to_dict(self) -> dict:
        """Convert interaction to dictionary.

        Returns:
            Dictionary representation of interaction
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "dataset_id": self.dataset_id,
            "interaction_type": self.interaction_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.meta_data or {},
        }


class UserPreference(Base):
    """UserPreference model for learned user preferences.

    Stores denormalized user preferences learned from search history
    and interactions. Updated periodically by preference learning algorithm.
    One-to-one relationship with User.
    """

    __tablename__ = "user_preferences"

    # Primary key (also foreign key)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="User these preferences belong to",
    )

    # Learned preferences (JSONB arrays for flexibility)
    preferred_organisms = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="List of preferred organisms (e.g., ['Homo sapiens', 'Mus musculus'])",
    )

    preferred_diseases = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="List of preferred diseases/conditions",
    )

    preferred_genes = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="List of preferred genes of interest",
    )

    preferred_platforms = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="List of preferred sequencing platforms",
    )

    preferred_tissues = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="List of preferred tissue types",
    )

    preferred_sample_types = Column(
        JSONB,
        nullable=True,
        default=list,
        comment="List of preferred sample types",
    )

    # Quality thresholds
    quality_thresholds = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Quality thresholds (min_samples, min_quality_score, etc.)",
    )

    # Search filters
    default_filters = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Default search filters to apply",
    )

    # Timestamp
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last preference update timestamp",
    )

    # Learning metadata
    learning_metadata = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Metadata about preference learning (confidence scores, sample sizes, etc.)",
    )

    # Relationships
    user = relationship("User", back_populates="user_preference")

    def __repr__(self) -> str:
        """String representation of UserPreference."""
        organisms = self.preferred_organisms or []
        diseases = self.preferred_diseases or []
        return (
            f"<UserPreference(user_id={self.user_id}, "
            f"organisms={len(organisms)}, "
            f"diseases={len(diseases)})>"
        )

    def to_dict(self) -> dict:
        """Convert preferences to dictionary.

        Returns:
            Dictionary representation of preferences
        """
        return {
            "user_id": str(self.user_id),
            "preferred_organisms": self.preferred_organisms or [],
            "preferred_diseases": self.preferred_diseases or [],
            "preferred_genes": self.preferred_genes or [],
            "preferred_platforms": self.preferred_platforms or [],
            "preferred_tissues": self.preferred_tissues or [],
            "preferred_sample_types": self.preferred_sample_types or [],
            "quality_thresholds": self.quality_thresholds or {},
            "default_filters": self.default_filters or {},
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "learning_metadata": self.learning_metadata or {},
        }
