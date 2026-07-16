"""Add composite indexes for cross-conversation dataset recall

Revision ID: 003
Revises: 002
Create Date: 2025-11-25 03:49:00

This migration adds composite indexes to the user_interactions table
to optimize cross-conversation dataset recall queries:
- idx_interactions_user_created: (user_id, created_at) for recalled datasets
- idx_interactions_dataset_user: (dataset_id, user_id) for dataset conversations
- idx_interactions_conversation: (conversation_id) for conversation queries
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '003_add_interaction_indexes'
down_revision: Union[str, None] = '002_add_conversation_tags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for optimized cross-conversation queries."""
    # Create composite index for cross-conversation recall queries (user_id, created_at)
    op.create_index(
        'idx_interactions_user_created',
        'user_interactions',
        ['user_id', 'created_at'],
        unique=False
    )

    # Create composite index for dataset conversation queries (dataset_id, user_id)
    op.create_index(
        'idx_interactions_dataset_user',
        'user_interactions',
        ['dataset_id', 'user_id'],
        unique=False
    )

    # Create index on conversation_id for conversation-specific queries
    op.create_index(
        'idx_interactions_conversation',
        'user_interactions',
        ['conversation_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove composite indexes."""
    op.drop_index('idx_interactions_conversation', table_name='user_interactions')
    op.drop_index('idx_interactions_dataset_user', table_name='user_interactions')
    op.drop_index('idx_interactions_user_created', table_name='user_interactions')
