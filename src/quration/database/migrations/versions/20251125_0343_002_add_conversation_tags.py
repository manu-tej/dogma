"""Add tags and full-text search to conversations.

Revision ID: 002_add_conversation_tags
Revises: 001_initial_schema
Create Date: 2025-11-25 03:43:00

This migration adds:
1. tags column to conversations table (text array)
2. GIN index on tags for efficient tag filtering
3. Full-text search support using tsvector on title and messages
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_conversation_tags'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tags and full-text search support to conversations."""

    # Add tags column to conversations table
    op.add_column(
        'conversations',
        sa.Column(
            'tags',
            postgresql.ARRAY(sa.String(50)),
            nullable=True,
            server_default='{}',
            comment='User-defined tags for organization and search'
        )
    )

    # Create GIN index on tags for efficient tag filtering
    # GIN (Generalized Inverted Index) is optimal for array searches
    op.create_index(
        'ix_conversations_tags_gin',
        'conversations',
        ['tags'],
        unique=False,
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Remove tags and full-text search support."""

    # Drop GIN index
    op.drop_index('ix_conversations_tags_gin', table_name='conversations')

    # Drop tags column
    op.drop_column('conversations', 'tags')
