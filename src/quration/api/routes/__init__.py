"""API route handlers for context memory endpoints."""

from quration.api.routes.context import router as context_router
from quration.api.routes.health import router as health_router
from quration.api.routes.interactions import (
    context_router as interactions_legacy_router,
)
from quration.api.routes.interactions import router as interactions_router
from quration.api.routes.preferences import router as preferences_router
from quration.api.routes.searches import context_router as searches_legacy_router
from quration.api.routes.searches import router as searches_router

__all__ = [
    "context_router",
    "health_router",
    "interactions_router",
    "interactions_legacy_router",
    "preferences_router",
    "searches_router",
    "searches_legacy_router",
]
