# Integration Tests for Context Memory Module

This directory contains comprehensive integration tests for the context memory module, covering conversation persistence, search storage, interaction tracking, preferences, and cache synchronization.

## Test Files

| File | Tests | Purpose |
|------|-------|---------|
| `test_conversation_persistence.py` | 15 | Conversation CRUD, message ordering, cache integration |
| `test_search_storage.py` | 13 | Search persistence, result pagination, query specs |
| `test_interaction_tracking.py` | 15 | User interactions, stats, history, recalled datasets |
| `test_preferences.py` | 18 | Preference CRUD, filtering, analysis, acceptance |
| `test_cache_sync.py` | 13 | Write-through, cache-aside, invalidation, consistency |
| **Total** | **74** | **Complete integration test suite** |

## Prerequisites

Install test dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov aiosqlite redis
```

Or if using the project's optional dependencies:

```bash
pip install -e ".[dev,database]"
```

## Running Tests

### Run All Integration Tests

```bash
pytest tests/integration/ -v
```

### Run Specific Test File

```bash
pytest tests/integration/test_conversation_persistence.py -v
```

### Run Specific Test Class

```bash
pytest tests/integration/test_conversation_persistence.py::TestConversationPersistence -v
```

### Run Specific Test

```bash
pytest tests/integration/test_conversation_persistence.py::TestConversationPersistence::test_create_conversation_with_messages -v
```

## Coverage Reports

### Generate Coverage Report

```bash
pytest tests/integration/ --cov=src/quration --cov-report=term --cov-report=html
```

This will:
- Print coverage summary to terminal
- Generate HTML report in `htmlcov/index.html`

### View Coverage Report

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Target

**Target:** >90% coverage for context persistence module

**Modules Covered:**
- `src/quration/services/context_service.py`
- `src/quration/repositories/conversation.py`
- `src/quration/repositories/search.py`
- `src/quration/repositories/interaction.py`
- `src/quration/repositories/user.py`
- `src/quration/cache/services/*.py`

## Test Infrastructure

### Database

Tests use **SQLite in-memory database** for:
- Fast execution
- Complete isolation between tests
- No external dependencies
- Automatic cleanup

Each test gets a fresh database session that rolls back after the test.

### Cache

Tests support **Redis cache** with graceful degradation:
- If Redis is available: Tests run with full cache integration
- If Redis is unavailable: Tests automatically skip cache-specific tests
- Cache is automatically reset between tests

### Fixtures

The `conftest.py` provides comprehensive fixtures:

**Database:**
- `async_engine` - Async SQLite engine
- `async_db_session` - Session with auto-rollback

**Cache:**
- `redis_client` - Redis client with graceful degradation

**Users:**
- `test_user` - Primary test user
- `test_user_2` - Secondary user for multi-user tests

**Conversations:**
- `test_conversation` - Conversation with 3 messages
- `empty_conversation` - Empty conversation

**Repositories:**
- `conversation_repo` - ConversationRepository
- `search_repo` - SearchRepository
- `user_repo` - UserRepository
- `interaction_repo` - InteractionRepository

**Services:**
- `context_service` - ContextService with all repositories

**Sample Data:**
- `sample_search_results` - 3 sample datasets
- `sample_query_spec` - Complete query specification
- `sample_preferences` - 3 user preferences
- `large_message_list` - 100 messages for stress testing
- `large_search_results` - 50 results for pagination testing

## Test Patterns

### Async Tests

All tests use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_something(async_db_session, test_user):
    # Test code here
    result = await some_async_function()
    assert result is not None
```

### Cache-Aware Tests

Tests that require Redis check availability:

```python
@pytest.mark.asyncio
async def test_cache_integration(redis_client):
    if not redis_client.is_available():
        pytest.skip("Redis not available")

    # Test code here
```

### Data Isolation

Each test uses a fresh database session:

```python
@pytest.mark.asyncio
async def test_something(async_db_session, conversation_repo):
    # Create test data
    conv = await conversation_repo.create_conversation(...)
    await async_db_session.commit()

    # Test assertions
    assert conv.id is not None

    # Automatic rollback after test
```

## Debugging Tests

### Run with Detailed Output

```bash
pytest tests/integration/ -vv -s
```

Flags:
- `-vv` - Very verbose output
- `-s` - Show print statements

### Run with Debug on Failure

```bash
pytest tests/integration/ --pdb
```

This will drop into Python debugger on test failures.

### Run Specific Test with Logs

```bash
pytest tests/integration/test_conversation_persistence.py::test_name -vv --log-cli-level=DEBUG
```

## Common Issues

### "Redis not available"

Some tests are skipped if Redis is not running. To run all tests:

```bash
# Start Redis
redis-server

# Run tests
pytest tests/integration/ -v
```

### "Module not found" errors

Install all dependencies:

```bash
pip install -e ".[dev,database]"
```

### Async warnings

Make sure pytest-asyncio is installed:

```bash
pip install pytest-asyncio
```

## Contributing

When adding new integration tests:

1. **Use existing fixtures** - Leverage `conftest.py` fixtures
2. **Mark as async** - All tests should use `@pytest.mark.asyncio`
3. **Document tests** - Add clear docstrings
4. **Check cache availability** - Skip cache tests if Redis unavailable
5. **Clean up** - Let session rollback handle cleanup
6. **Test edge cases** - Include large datasets, concurrent ops
7. **Verify consistency** - Check cache-DB consistency

## Test Organization

```
tests/integration/
├── __init__.py                          # Package initialization
├── conftest.py                          # Shared fixtures
├── README.md                            # This file
├── test_conversation_persistence.py     # Conversation tests
├── test_search_storage.py               # Search tests
├── test_interaction_tracking.py         # Interaction tests
├── test_preferences.py                  # Preference tests
└── test_cache_sync.py                   # Cache sync tests
```

## Performance

Integration tests are designed to be fast:
- In-memory database (no disk I/O)
- Minimal test data
- Efficient fixtures
- Parallel execution supported

Typical execution time: **<30 seconds** for all 74 tests.

## CI/CD Integration

These tests are ready for CI/CD:
- No external dependencies (except optional Redis)
- Deterministic (no random data)
- Isolated (no shared state)
- Fast execution
- Clear pass/fail criteria

Example CI configuration:

```yaml
test:
  script:
    - pip install -e ".[dev,database]"
    - pytest tests/integration/ --cov --cov-report=xml
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

## Questions?

For questions or issues with integration tests, check:
1. Test docstrings for detailed explanations
2. `conftest.py` for fixture implementations
3. Scratch notes in `scratch_notes/integration_tests_*.md`
