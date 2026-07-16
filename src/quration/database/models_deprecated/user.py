"""User model for Context Memory Module."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, String, func
from sqlalchemy.dialects.postgresql import UUID
from quration.database.types import JSONB
from sqlalchemy.orm import relationship

from quration.database.connection import Base

if TYPE_CHECKING:
    from quration.database.models.conversation import Conversation
    from quration.database.models.interaction import UserInteraction, UserPreference
    from quration.database.models.search import Search


class User(Base):
    """User model for authentication and preferences.

    Stores user account information and high-level preferences.
    Detailed preferences are stored in UserPreference model.
    """

    __tablename__ = "users"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique user identifier",
    )

    # User identification
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (unique)",
    )

    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Account creation timestamp",
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )

    # User preferences and settings (JSONB for flexibility)
    preferences = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="General user preferences (theme, notifications, etc.)",
    )

    settings = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Application settings (language, timezone, etc.)",
    )

    # Relationships
    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    searches = relationship(
        "Search",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    interactions = relationship(
        "UserInteraction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    user_preference = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, email={self.email})>"

    def to_dict(self) -> dict:
        """Convert user to dictionary.

        Returns:
            Dictionary representation of user
        """
        return {
            "id": str(self.id),
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "preferences": self.preferences or {},
            "settings": self.settings or {},
        }
