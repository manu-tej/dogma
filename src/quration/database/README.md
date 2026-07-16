# Quration Database Module

PostgreSQL database layer for the Context Memory Module, providing persistent storage for conversations, user preferences, search history, and user interactions.

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[database]"
```

### 2. Set Database URL

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/quration"
```

### 3. Run Migrations

```bash
# Create all tables
alembic upgrade head

# Check status
alembic current
```

### 4. Use in Code

```python
from quration.database import init_db, db_session_scope
from quration.database.models import User, Conversation
from quration.config import get_config

# Initialize
config = get_config()
init_db(config.database.database_url)

# Use database
with db_session_scope() as session:
    user = User(email="researcher@example.com")
    session.add(user)
```

## Schema Overview

### Tables

1. **users** - User accounts and settings
2. **conversations** - Chat sessions
3. **messages** - Individual messages in conversations
4. **searches** - Search queries and metadata
5. **search_results** - Denormalized search results
6. **user_interactions** - Dataset interaction tracking
7. **user_preferences** - Learned user preferences

### Relationships

```
users (1) ──< conversations (N)
         └──< searches (N)
         └──< user_interactions (N)
         └─── user_preferences (1)

conversations (1) ──< messages (N)
                  └──< searches (N)

searches (1) ──< search_results (N)
```

## Usage Examples

### Creating Records

```python
from quration.database import db_session_scope
from quration.database.models import User, Conversation, Message

with db_session_scope() as session:
    # Create user
    user = User(
        email="researcher@example.com",
        preferences={"theme": "dark"},
        settings={"language": "en"}
    )
    session.add(user)
    session.flush()

    # Create conversation
    conversation = Conversation(
        user_id=user.id,
        title="Melanoma Research",
        metadata={
            "datasets_explored": ["GSE12345"],
            "research_focus": ["melanoma", "immunotherapy"]
        }
    )
    session.add(conversation)
    session.flush()

    # Create message
    message = Message(
        conversation_id=conversation.id,
        role="user",
        content="Find melanoma RNA-seq datasets",
        metadata={"entities": {"diseases": ["melanoma"]}}
    )
    session.add(message)
```

### Querying Records

```python
from quration.database import db_session_scope
from quration.database.models import User, Conversation
from datetime import datetime, timedelta

with db_session_scope() as session:
    # Get user by email
    user = session.query(User).filter_by(
        email="researcher@example.com"
    ).first()

    # Get recent conversations
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    conversations = (
        session.query(Conversation)
        .filter(
            Conversation.user_id == user.id,
            Conversation.created_at >= thirty_days_ago,
            Conversation.is_archived == False
        )
        .order_by(Conversation.updated_at.desc())
        .limit(10)
        .all()
    )

    # Get conversation with messages
    conversation = (
        session.query(Conversation)
        .filter_by(id=conversation_id)
        .first()
    )
    messages = conversation.messages  # Uses relationship
```

### Tracking Interactions

```python
from quration.database import db_session_scope
from quration.database.models import UserInteraction

with db_session_scope() as session:
    interaction = UserInteraction(
        user_id=user.id,
        dataset_id="GSE12345",
        interaction_type="analyzed",
        metadata={
            "analysis_type": "differential_expression",
            "parameters": {"fdr": 0.05}
        }
    )
    session.add(interaction)
```

### Storing Search Results

```python
from quration.database import db_session_scope
from quration.database.models import Search, SearchResult

with db_session_scope() as session:
    # Create search
    search = Search(
        user_id=user.id,
        conversation_id=conversation.id,
        query_text="melanoma RNA-seq",
        query_spec={
            "disease": "melanoma",
            "experiment_type": "RNA-seq"
        },
        results_count=10
    )
    session.add(search)
    session.flush()

    # Create search results
    for i, dataset in enumerate(datasets):
        result = SearchResult(
            search_id=search.id,
            dataset_id=dataset["accession"],
            rank=i,
            title=dataset["title"],
            organism=dataset["organism"],
            sample_count=dataset["sample_count"],
            dataset_details=dataset
        )
        session.add(result)
```

### Managing User Preferences

```python
from quration.database import db_session_scope
from quration.database.models import UserPreference

with db_session_scope() as session:
    # Create or update preferences
    preferences = (
        session.query(UserPreference)
        .filter_by(user_id=user.id)
        .first()
    )

    if not preferences:
        preferences = UserPreference(user_id=user.id)
        session.add(preferences)

    # Update preferences
    preferences.preferred_organisms = ["Homo sapiens", "Mus musculus"]
    preferences.preferred_diseases = ["melanoma", "lung cancer"]
    preferences.quality_thresholds = {
        "min_samples": 30,
        "min_quality_score": 0.8
    }
```

## Configuration

### Environment Variables

```bash
# Database connection
DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# Connection pool settings (optional)
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
DATABASE_POOL_PRE_PING=true

# Debugging (optional)
DATABASE_ECHO_SQL=false
```

### Config Object

```python
from quration.config import get_config

config = get_config()

# Access database config
db_url = config.database.database_url
pool_size = config.database.pool_size
```

## Migrations

### Create New Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Create empty migration
alembic revision -m "Description of changes"
```

### Apply Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Upgrade to specific revision
alembic upgrade abc123
```

### Rollback Migrations

```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade abc123

# Downgrade all (drop all tables)
alembic downgrade base
```

### Check Status

```bash
# Current version
alembic current

# Migration history
alembic history

# Show SQL without executing
alembic upgrade head --sql
```

## Connection Management

### Using Context Manager (Recommended)

```python
from quration.database import db_session_scope

with db_session_scope() as session:
    # Do database operations
    user = session.query(User).first()
    # Auto-commit on success, auto-rollback on error
```

### Manual Session Management

```python
from quration.database import get_db_session

session = get_db_session()
try:
    # Do database operations
    user = session.query(User).first()
    session.commit()
except Exception:
    session.rollback()
    raise
finally:
    session.close()
```

### Connection Pooling

The database uses SQLAlchemy's QueuePool with the following defaults:

- **pool_size**: 5 persistent connections
- **max_overflow**: 10 additional connections during peak load
- **pool_timeout**: 30 seconds to wait for available connection
- **pool_recycle**: 3600 seconds (1 hour) before recycling connections
- **pool_pre_ping**: Enabled (test connections before use)

## Performance Tips

### 1. Use Indexes

All foreign keys and frequently queried columns are indexed. Additional indexes can be added via migrations.

### 2. Batch Operations

```python
# Good - batch insert
with db_session_scope() as session:
    messages = [Message(...) for _ in range(100)]
    session.bulk_save_objects(messages)

# Bad - individual inserts
for _ in range(100):
    with db_session_scope() as session:
        session.add(Message(...))
```

### 3. Lazy Loading

Use `joinedload` or `selectinload` to avoid N+1 queries:

```python
from sqlalchemy.orm import joinedload

with db_session_scope() as session:
    conversations = (
        session.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter_by(user_id=user.id)
        .all()
    )
```

### 4. JSONB Queries

PostgreSQL supports efficient JSONB queries:

```python
from sqlalchemy import func

# Query JSONB field
conversations = (
    session.query(Conversation)
    .filter(
        Conversation.metadata['research_focus'].contains(['melanoma'])
    )
    .all()
)
```

## Testing

### Setup Test Database

```python
import pytest
from quration.database import DatabaseConnection, Base
from quration.database.models import User

@pytest.fixture
def db():
    """Create test database."""
    db = DatabaseConnection("postgresql://localhost:5432/quration_test")
    db.initialize()
    Base.metadata.create_all(db.engine)
    yield db
    Base.metadata.drop_all(db.engine)
    db.close()

def test_create_user(db):
    with db.session_scope() as session:
        user = User(email="test@example.com")
        session.add(user)

    with db.session_scope() as session:
        user = session.query(User).filter_by(email="test@example.com").first()
        assert user is not None
```

## Troubleshooting

### Connection Issues

```python
# Test connection
from quration.database import init_db

try:
    db = init_db("postgresql://localhost:5432/quration")
    print("Connected successfully!")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Migration Issues

```bash
# Check Alembic can find models
python -c "from quration.database.models import User; print(User.__table__)"

# Verify DATABASE_URL
echo $DATABASE_URL

# Check migration status
alembic current
```

### Pool Exhaustion

If you see "QueuePool limit exceeded", increase pool size:

```python
init_db(
    database_url,
    pool_size=10,
    max_overflow=20
)
```

## API Reference

### Models

- **User** - `quration.database.models.User`
- **Conversation** - `quration.database.models.Conversation`
- **Message** - `quration.database.models.Message`
- **Search** - `quration.database.models.Search`
- **SearchResult** - `quration.database.models.SearchResult`
- **UserInteraction** - `quration.database.models.UserInteraction`
- **UserPreference** - `quration.database.models.UserPreference`

### Functions

- **init_db(url, \*\*kwargs)** - Initialize database connection
- **get_db_session()** - Get new session from global connection
- **db_session_scope()** - Context manager for transactions

### Classes

- **DatabaseConnection** - Manages connections and sessions
- **Base** - SQLAlchemy declarative base for all models

## Contributing

When adding new models or fields:

1. Create/update model in `models/` directory
2. Import model in `models/__init__.py`
3. Import model in `migrations/env.py`
4. Generate migration: `alembic revision --autogenerate -m "description"`
5. Review and test migration
6. Update documentation

## License

MIT License - See project root for details.
