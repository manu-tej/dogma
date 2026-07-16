"""Initial database schema for Context Memory Module.

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-11-19 05:24:00

This migration creates all 7 tables for the Context Memory Module Phase 1 MVP:
1. users - User authentication and preferences
2. conversations - Conversation metadata
3. messages - Chat messages (user and assistant)
4. searches - Search queries executed
5. search_results - Denormalized search results for performance
6. user_interactions - Track dataset views/analyzes
7. user_preferences - Learned user preferences

All indexes from the PRD are included for optimal query performance.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables and indexes for Context Memory Module."""

    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique user identifier'),
        sa.Column('email', sa.String(length=255), nullable=False, comment='User email address (unique)'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Account creation timestamp'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='General user preferences (theme, notifications, etc.)'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Application settings (language, timezone, etc.)'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        comment='User accounts and settings'
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # 2. Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique conversation identifier'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User who owns this conversation'),
        sa.Column('title', sa.String(length=500), nullable=True, comment='Conversation title (auto-generated or user-provided)'),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Optional project/research group identifier'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='Whether conversation is archived'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Conversation creation timestamp'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last message timestamp'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Conversation metadata (datasets explored, topics, etc.)'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Conversation sessions'
    )
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'], unique=False)
    op.create_index('ix_conversations_created_at', 'conversations', ['created_at'], unique=False)
    op.create_index('ix_conversations_is_archived', 'conversations', ['is_archived'], unique=False)
    op.create_index('ix_conversations_project_id', 'conversations', ['project_id'], unique=False)

    # 3. Create messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique message identifier'),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Conversation this message belongs to'),
        sa.Column('role', sa.String(length=20), nullable=False, comment="Message role: 'user' or 'assistant'"),
        sa.Column('content', sa.Text(), nullable=False, comment='Message text content'),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Message creation timestamp'),
        sa.Column('embedding_id', sa.String(length=100), nullable=True, comment='Reference to vector database embedding'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Message metadata (entities, reasoning, etc.)'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Chat messages'
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False)
    op.create_index('ix_messages_timestamp', 'messages', ['timestamp'], unique=False)
    op.create_index('ix_messages_role', 'messages', ['role'], unique=False)
    op.create_index('ix_messages_embedding_id', 'messages', ['embedding_id'], unique=False)

    # 4. Create searches table
    op.create_table(
        'searches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique search identifier'),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Conversation this search belongs to (optional)'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User who executed this search'),
        sa.Column('query_text', sa.Text(), nullable=False, comment='Natural language query text'),
        sa.Column('query_spec', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Structured query parameters (organism, disease, etc.)'),
        sa.Column('results_count', sa.Integer(), nullable=True, comment='Number of results returned'),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='Whether search completed successfully'),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Search execution timestamp'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Additional search metadata (execution time, filters, etc.)'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Search queries and metadata'
    )
    op.create_index('ix_searches_user_id', 'searches', ['user_id'], unique=False)
    op.create_index('ix_searches_conversation_id', 'searches', ['conversation_id'], unique=False)
    op.create_index('ix_searches_timestamp', 'searches', ['timestamp'], unique=False)

    # 5. Create search_results table
    op.create_table(
        'search_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique search result identifier'),
        sa.Column('search_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Search this result belongs to'),
        sa.Column('dataset_id', sa.String(length=50), nullable=False, comment='Dataset identifier (e.g., GSE12345)'),
        sa.Column('rank', sa.Integer(), nullable=False, comment='Position in search results (0-indexed)'),
        sa.Column('title', sa.String(length=1000), nullable=True, comment='Dataset title'),
        sa.Column('summary', sa.Text(), nullable=True, comment='Dataset summary/description'),
        sa.Column('organism', sa.String(length=200), nullable=True, comment='Organism name'),
        sa.Column('sample_count', sa.Integer(), nullable=True, comment='Number of samples in dataset'),
        sa.Column('relevance_score', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Relevance scoring details'),
        sa.Column('dataset_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Complete dataset metadata'),
        sa.ForeignKeyConstraint(['search_id'], ['searches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Denormalized search results for performance'
    )
    op.create_index('ix_search_results_search_id', 'search_results', ['search_id'], unique=False)
    op.create_index('ix_search_results_dataset_id', 'search_results', ['dataset_id'], unique=False)
    op.create_index('ix_search_results_organism', 'search_results', ['organism'], unique=False)

    # 6. Create user_interactions table
    op.create_table(
        'user_interactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique interaction identifier'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User who performed this interaction'),
        sa.Column('dataset_id', sa.String(length=50), nullable=False, comment='Dataset identifier (e.g., GSE12345)'),
        sa.Column('interaction_type', sa.String(length=50), nullable=False, comment='Type of interaction: viewed, analyzed, exported, downloaded'),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Interaction timestamp'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Interaction metadata (analysis type, filters, etc.)'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='User interactions with datasets'
    )
    op.create_index('ix_user_interactions_user_id', 'user_interactions', ['user_id'], unique=False)
    op.create_index('ix_user_interactions_dataset_id', 'user_interactions', ['dataset_id'], unique=False)
    op.create_index('ix_user_interactions_interaction_type', 'user_interactions', ['interaction_type'], unique=False)
    op.create_index('ix_user_interactions_timestamp', 'user_interactions', ['timestamp'], unique=False)

    # 7. Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User these preferences belong to'),
        sa.Column('preferred_organisms', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="List of preferred organisms (e.g., ['Homo sapiens', 'Mus musculus'])"),
        sa.Column('preferred_diseases', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of preferred diseases/conditions'),
        sa.Column('preferred_genes', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of preferred genes of interest'),
        sa.Column('preferred_platforms', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of preferred sequencing platforms'),
        sa.Column('preferred_tissues', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of preferred tissue types'),
        sa.Column('preferred_sample_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of preferred sample types'),
        sa.Column('quality_thresholds', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Quality thresholds (min_samples, min_quality_score, etc.)'),
        sa.Column('default_filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Default search filters to apply'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last preference update timestamp'),
        sa.Column('learning_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Metadata about preference learning (confidence scores, sample sizes, etc.)'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
        comment='Learned user preferences'
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('user_preferences')
    op.drop_table('user_interactions')
    op.drop_table('search_results')
    op.drop_table('searches')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')
