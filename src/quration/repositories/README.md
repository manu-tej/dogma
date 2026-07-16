# Quration Repository Layer

The repository layer provides a clean data access abstraction for the Quration context memory system. It implements the Repository pattern with integrated caching for optimal performance.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                              │
│            context_service.py - Business logic               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Repository Layer                           │
│  ┌──────────────┬──────────────┬──────────────┬──────────┐  │
│  │Conversation  │  Search      │    User      │Interaction│ │
│  │Repository    │  Repository  │  Repository  │Repository │ │
│  └──────────────┴──────────────┴──────────────┴──────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
          ┌─────────────────┐   ┌─────────────────┐
          │  Cache (Redis)  │   │  DB (PostgreSQL)│
          │  Check first    │   │  Fallback       │
          └─────────────────┘   └─────────────────┘
```

## Components

### Base Repository (`base.py`)

Generic CRUD operations for all repositories:
- `create(**kwargs)` - Create a new record
- `get_by_id(id)` - Get record by UUID
- `get_all(limit, offset)` - List all records with pagination
- `update(id, **kwargs)` - Update record
- `delete(id)` - Delete record
- `count(filter_dict)` - Count records
- `find_one(filter_dict)` - Find single record
- `find_many(filter_dict, limit, offset, order_by, desc)` - Find multiple records

### ConversationRepository (`conversation.py`)

Manages conversations and messages:
- `create_conversation(user_id, title, metadata)` - Create new conversation
- `get_conversation(conversation_id, use_cache)` - Get conversation with messages
- `list_user_conversations(user_id, limit, offset)` - List user's conversations
- `update_conversation(conversation_id, title, metadata)` - Update conversation
- `archive_conversation(conversation_id)` - Soft delete conversation
- `add_message(conversation_id, role, content, metadata)` - Add message
- `get_conversation_messages(conversation_id, limit, offset)` - Get messages
- `update_conversation_metadata(conversation_id, metadata_updates)` - Update metadata

**Cache Strategy:**
- Key: `conv:{conversation_id}:context`
- TTL: 24 hours
- Invalidation: On update, delete, or new message

### SearchRepository (`search.py`)

Manages searches and results:
- `save_search(conversation_id, user_id, query_spec, result_count, execution_time_ms)` - Save search
- `get_search(search_id, use_cache)` - Get search with results
- `get_user_searches(user_id, limit, offset, conversation_id)` - List user's searches
- `get_conversation_searches(conversation_id, limit, offset)` - Get conversation's searches
- `save_search_results(search_id, results)` - Bulk insert results (optimized for 100+ results)
- `get_search_results(search_id, limit, offset)` - Get search results
- `get_dataset_searches(dataset_id, user_id, limit)` - Find searches containing dataset
- `find_similar_searches(user_id, query_spec, limit)` - Semantic search (future)

**Cache Strategy:**
- Key: `search:{search_id}:results`
- TTL: 1 hour
- Invalidation: On update

**Performance:**
- Bulk insert optimized for 100+ results
- Query performance target: < 100ms for 95th percentile

### UserRepository (`user.py`)

Manages users and preferences:
- `create_user(external_id)` - Create new user
- `get_user(user_id)` - Get user by UUID
- `get_user_by_external_id(external_id)` - Get user by external ID
- `get_or_create_user(external_id)` - Get existing or create new user
- `get_user_preferences(user_id, use_cache)` - Get all preferences
- `save_preference(user_id, preference_type, preference_value, confidence_score)` - Save preference
- `get_preference_by_type(user_id, preference_type)` - Get specific preference
- `update_preference(preference_id, preference_value, confidence_score)` - Update preference
- `delete_preference(preference_id)` - Delete preference
- `get_high_confidence_preferences(user_id, min_confidence)` - Get high-confidence preferences

**Cache Strategy:**
- Key: `user:{user_id}:prefs`
- TTL: 7 days
- Invalidation: On preference update/delete

### InteractionRepository (`interaction.py`)

Tracks user interactions with datasets:
- `record_interaction(user_id, dataset_id, interaction_type, conversation_id, search_id, metadata)` - Record interaction
- `get_user_interactions(user_id, dataset_id, interaction_type, limit, offset)` - Get user's interactions
- `get_dataset_interaction_history(dataset_id, user_id, limit, offset)` - Get dataset history
- `has_user_viewed_dataset(user_id, dataset_id)` - Check if viewed
- `get_user_viewed_datasets(user_id, limit, offset)` - List viewed datasets
- `get_interaction_stats(user_id)` - Get statistics
- `get_conversation_interactions(conversation_id, limit, offset)` - Get conversation's interactions
- `get_recent_interactions(user_id, dataset_id, limit)` - Get recent interactions

**Interaction Types:**
- `view` - User viewed dataset
- `analyze` - User analyzed dataset
- `download` - User downloaded dataset

**Cache Strategy:**
- Key: `user:{user_id}:dataset:{dataset_id}:interactions`
- TTL: 1 hour
- Invalidation: On new interaction

## Context Service

High-level service combining repositories:

### Methods

- `get_conversation_context(conversation_id, use_cache)` - Get full context (messages + searches + interactions)
- `restore_conversation_state(conversation_id)` - Restore for UI (includes search results)
- `create_conversation_with_message(user_id, role, content, title, metadata)` - Create conversation + initial message
- `save_search_with_results(conversation_id, user_id, query_spec, results, execution_time_ms)` - Atomic search save
- `track_dataset_interaction(user_id, dataset_id, interaction_type, ...)` - Track interaction
- `get_user_context_summary(user_id)` - Get user statistics
- `get_dataset_history(dataset_id, user_id)` - Get dataset interaction history

### Example Usage

```python
from quration.database import get_db_session
from quration.cache import RedisCache
from quration.services import ContextService

async def restore_conversation():
    cache = RedisCache()

    async with get_db_session() as session:
        service = ContextService(session, cache)

        # Restore full conversation state
        state = await service.restore_conversation_state(conversation_id)

        # Returns:
        # {
        #     "conversation": {...},
        #     "messages": [...],
        #     "searches": [
        #         {
        #             "id": "...",
        #             "query_spec": {...},
        #             "results": [...]  # Full results included
        #         }
        #     ],
        #     "interactions": [...]
        # }
```

## Database Models

All models use UUID primary keys and include timestamps:

- **User**: User accounts with external_id
- **Conversation**: Chat conversations with title and metadata
- **Message**: Individual messages with role and content
- **Search**: Search queries with query_spec (JSONB)
- **SearchResult**: Individual dataset results
- **UserInteraction**: User actions on datasets
- **UserPreference**: Learned preferences with confidence scores

See `database/models.py` for full schema.

## Caching Strategy

### Cache-Aside Pattern

1. Check cache first
2. On cache miss, load from database
3. Store in cache for future requests
4. Invalidate cache on updates

### TTL Policies

- Conversations: 24 hours
- User Preferences: 7 days
- Search Results: 1 hour
- Interactions: 1 hour

### Cache Keys

```python
from quration.cache.redis_client import (
    build_conversation_key,
    build_user_preferences_key,
    build_search_results_key,
    build_user_interactions_key,
)

conv_key = build_conversation_key(conversation_id)  # "conv:{id}:context"
prefs_key = build_user_preferences_key(user_id)     # "user:{id}:prefs"
search_key = build_search_results_key(search_id)    # "search:{id}:results"
inter_key = build_user_interactions_key(user_id, dataset_id)  # "user:{id}:dataset:{did}:interactions"
```

## Error Handling

All repositories raise `RepositoryError` on failures:

```python
from quration.repositories import RepositoryError

try:
    conversation = await conversation_repo.create_conversation(
        user_id=user_id,
        title="My Conversation"
    )
except RepositoryError as e:
    logger.error(f"Failed to create conversation: {e}")
```

## Transaction Management

Use session context for transactions:

```python
async with get_db_session() as session:
    repo = ConversationRepository(session)

    # All operations within this block are in a transaction
    conversation = await repo.create_conversation(...)
    message = await repo.add_message(...)

    # Commits automatically on exit
    # Rolls back on exception
```

For explicit control:

```python
async with get_db_session() as session:
    repo = ConversationRepository(session)

    try:
        conversation = await repo.create_conversation(...)
        message = await repo.add_message(...)

        await repo.commit()
    except Exception:
        await repo.rollback()
        raise
```

## Performance Targets

- Cache retrieval: < 50ms
- Database queries: < 100ms (95th percentile)
- Bulk insert (100 results): < 500ms
- Context restoration: < 2 seconds

## Best Practices

1. **Always use async/await**: All methods are async
2. **Use cache when possible**: Set `use_cache=True` for reads
3. **Batch operations**: Use bulk methods for multiple records
4. **Error handling**: Catch `RepositoryError` for database errors
5. **Transactions**: Use session context for atomic operations
6. **Pagination**: Always use limit/offset for large result sets
7. **Cache invalidation**: Automatic on updates, but be aware of patterns

## Testing

See `tests/test_repositories.py` for comprehensive test suite:

```bash
# Run repository tests
pytest tests/test_repositories.py -v

# Run with coverage
pytest tests/test_repositories.py --cov=quration.repositories

# Run integration tests (requires PostgreSQL)
pytest tests/integration/test_repositories_integration.py -v
```

## Future Enhancements

1. **Semantic Search**: Implement `find_similar_searches()` with embeddings
2. **Query Optimization**: Add query result caching at ORM level
3. **Batch Operations**: Add more bulk insert/update methods
4. **Cache Warming**: Implement background cache refresh
5. **Metrics**: Add performance metrics and monitoring
6. **Read Replicas**: Support read replica routing
7. **Sharding**: Add sharding support for high scale

## See Also

- [Database Models](../database/models.py)
- [Cache Client](../cache/redis_client.py)
- [Context Service](../services/context_service.py)
- [Example Usage](../../examples/repository_usage_example.py)
