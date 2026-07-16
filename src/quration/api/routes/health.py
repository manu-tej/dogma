"""Health check API endpoints.

This module provides health check endpoints for monitoring system status:
- Overall system health
- Database health
- Cache health
- Readiness probe for Kubernetes
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from quration.api.dependencies import get_async_session, get_redis_cache
from quration.cache.redis_client import RedisClient
from quration.utils.health import (
    check_database_health,
    check_redis_health,
    check_system_health,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Overall system health check")
@router.get("/", include_in_schema=False)  # Duplicate for trailing slash
async def health_check(
    session: AsyncSession = Depends(get_async_session),
    redis_client: RedisClient = Depends(get_redis_cache),
) -> dict[str, Any]:
    """Check overall system health.

    This endpoint aggregates health status from all system components
    and returns a comprehensive health report.

    Returns:
        - 200: System is healthy or degraded but operational
        - 503: System is unhealthy (database unavailable)

    Response includes:
    - healthy: Overall health flag
    - status: "healthy", "degraded", or "unhealthy"
    - message: Summary message
    - components: Individual component health status
    """
    try:
        health = await check_system_health(session, redis_client)

        # Return 503 if system is unhealthy (database down)
        if not health["healthy"] and health["status"] == "unhealthy":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health,
            )

        # Return 200 for healthy or degraded (degraded means working without cache)
        return health

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "healthy": False,
                "status": "error",
                "message": f"Health check error: {str(e)}",
                "components": {},
            },
        )


@router.get("/db", summary="Database health check")
async def database_health_check(
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Check database connectivity and health.

    This endpoint verifies PostgreSQL database is accessible and responsive.

    Returns:
        - 200: Database is healthy
        - 503: Database is unavailable

    Response includes:
    - healthy: Health flag
    - message: Status message
    - details: Database version and connection pool stats
    """
    try:
        health = await check_database_health(session)

        if not health["healthy"]:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health,
            )

        return health

    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "healthy": False,
                "message": f"Database health check error: {str(e)}",
                "details": {"error": str(e)},
            },
        )


@router.get("/cache", summary="Cache health check")
async def cache_health_check(
    redis_client: RedisClient = Depends(get_redis_cache),
) -> dict[str, Any]:
    """Check Redis cache availability and health.

    This endpoint verifies Redis cache is accessible. Note that the system
    can operate without cache (in degraded mode), so this is informational.

    Returns:
        - 200: Cache is healthy or disabled (system operational)
        - 503: Cache is enabled but unavailable

    Response includes:
    - healthy: Health flag
    - message: Status message
    - details: Redis connection info and pool stats
    """
    try:
        health = check_redis_health(redis_client)

        # If Redis is disabled, that's OK - return 200
        if not health["details"].get("enabled", False):
            return {
                "healthy": True,  # Not an error if disabled
                "message": "Redis cache is disabled",
                "details": health["details"],
            }

        # If Redis is enabled but unavailable, return 503
        if not health["healthy"]:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health,
            )

        return health

    except Exception as e:
        logger.error(f"Cache health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "healthy": False,
                "message": f"Cache health check error: {str(e)}",
                "details": {"error": str(e)},
            },
        )


@router.get("/ready", summary="Kubernetes readiness probe")
async def readiness_check(
    session: AsyncSession = Depends(get_async_session),
    redis_client: RedisClient = Depends(get_redis_cache),
) -> dict[str, Any]:
    """Kubernetes readiness probe endpoint.

    This endpoint indicates whether the application is ready to serve traffic.
    The service is ready if the database is accessible, regardless of cache status.

    Returns:
        - 200: Service is ready to accept traffic
        - 503: Service is not ready (database unavailable)

    Response includes:
    - ready: Readiness flag
    - message: Status message
    """
    try:
        health = await check_system_health(session, redis_client)

        # Ready if database is healthy (cache is optional)
        db_health = health.get("components", {}).get("database", {})
        ready = db_health.get("healthy", False)

        if not ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "ready": False,
                    "message": "Service not ready - database unavailable",
                },
            )

        # Include cache status in message but don't fail on it
        cache_health = health.get("components", {}).get("cache", {})
        cache_status = "available" if cache_health.get("healthy") else "unavailable"

        return {
            "ready": True,
            "message": f"Service ready (cache: {cache_status})",
        }

    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ready": False,
                "message": f"Readiness check error: {str(e)}",
            },
        )


@router.get("/liveness", summary="Kubernetes liveness probe")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe endpoint.

    This endpoint indicates whether the application is alive and should not be restarted.
    Always returns 200 unless the application is completely unresponsive.

    Returns:
        - 200: Application is alive
    """
    return {
        "alive": "true",
        "message": "Application is running",
    }
