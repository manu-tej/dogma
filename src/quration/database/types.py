"""Custom database types for SQLite compatibility."""

from sqlalchemy.types import TypeDecorator
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY


class JSONB(TypeDecorator):
    """Platform-independent JSONB type.

    Uses PostgreSQL's JSONB type on PostgreSQL, and falls back to
    JSON on other databases (e.g. SQLite during testing).
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        else:
            return dialect.type_descriptor(JSON())


class ARRAY(TypeDecorator):
    """Platform-independent ARRAY type.

    Uses PostgreSQL's ARRAY type on PostgreSQL, and falls back to
    JSON (storing arrays as JSON strings) on other databases (e.g. SQLite).
    """

    impl = JSON
    cache_ok = True

    def __init__(self, item_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.item_type = item_type

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(self.item_type))
        else:
            return dialect.type_descriptor(JSON())
