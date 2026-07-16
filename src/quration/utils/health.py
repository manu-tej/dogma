"""Health check utilities for system components.

This module provides health check functions for various system components:
- PostgreSQL database connectivity
- Redis cache availability
- Overall system health aggregation
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from quration.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)


async def check_database_health(session: AsyncSession) -> dict[str, Any]:
    """Check PostgreSQL database health.

    Performs a simple query to verify database connectivity and responsiveness.

    Args:
        session: Async database session

    Returns:
        Dictionary with health status:
        - healthy: True if database is accessible
        - message: Status message
        - details: Additional diagnostic information
    """
    health = {
        "healthy": False,
        "message": "",
        "details": {},
    }

    try:
        # Execute simple query to test connectivity
        result = await session.execute(text("SELECT 1"))
        row = result.scalar_one()

        if row == 1:
            health["healthy"] = True
            health["message"] = "Database is healthy and responsive"

            # Get database version
            try:
                version_result = await session.execute(text("SELECT version()"))
                version = version_result.scalar_one()
                health["details"]["version"] = version.split(",")[0]  # First part only
            except Exception as e:
                logger.warning(f"Failed to get database version: {e}")

            # Get connection pool stats if available
            try:
                pool = session.bind.pool if hasattr(session.bind, "pool") else None
                if pool:
                    health["details"]["pool"] = {
                        "size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                    }
            except Exception as e:
                logger.warning(f"Failed to get pool stats: {e}")

    except Exception as e:
        health["healthy"] = False
        health["message"] = f"Database health check failed: {str(e)}"
        health["details"]["error"] = str(e)
        logger.error(f"Database health check failed: {e}")

    return health


def check_redis_health(redis_client: Optional[RedisClient]) -> dict[str, Any]:
    """Check Redis cache health.

    Uses the RedisClient's built-in health check functionality.

    Args:
        redis_client: Redis client instance (can be None)

    Returns:
        Dictionary with health status:
        - healthy: True if Redis is accessible
        - message: Status message
        - details: Redis-specific information
    """
    if redis_client is None:
        return {
            "healthy": False,
            "message": "Redis client not initialized",
            "details": {"enabled": False},
        }

    try:
        # Use RedisClient's comprehensive health check
        health_info = redis_client.health_check()

        # Normalize to our health check format
        health = {
            "healthy": health_info.get("available", False),
            "message": health_info.get("message", "Unknown status"),
            "details": {
                "enabled": health_info.get("enabled", False),
                "connection_info": health_info.get("connection_info", {}),
                "pool_stats": health_info.get("pool_stats"),
            },
        }

        return health

    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "healthy": False,
            "message": f"Redis health check failed: {str(e)}",
            "details": {"error": str(e)},
        }


async def check_system_health(
    session: Optional[AsyncSession] = None,
    redis_client: Optional[RedisClient] = None,
) -> dict[str, Any]:
    """Aggregate health check for all system components.

    Checks database and cache health and returns overall system status.

    Args:
        session: Optional async database session
        redis_client: Optional Redis client instance

    Returns:
        Dictionary with overall health status:
        - healthy: True if all critical components are healthy
        - status: "healthy", "degraded", or "unhealthy"
        - components: Health status of individual components
        - message: Summary message
    """
    components = {}

    # Check database health (critical component)
    db_healthy = False
    if session:
        db_health = await check_database_health(session)
        components["database"] = db_health
        db_healthy = db_health["healthy"]
    else:
        components["database"] = {
            "healthy": False,
            "message": "Database session not provided",
        }

    # Check Redis health (non-critical, system can work without it)
    redis_healthy = True  # Default to true since it's optional
    if redis_client:
        redis_health = check_redis_health(redis_client)
        components["cache"] = redis_health
        redis_healthy = redis_health["healthy"]
    else:
        components["cache"] = {
            "healthy": False,
            "message": "Redis client not provided",
            "details": {"enabled": False},
        }

    # Determine overall health
    # System is healthy if database is up (Redis is optional)
    # System is degraded if database is up but Redis is down
    # System is unhealthy if database is down
    if db_healthy:
        if redis_healthy:
            status = "healthy"
            message = "All systems operational"
            overall_healthy = True
        else:
            status = "degraded"
            message = "Database operational, cache unavailable (degraded mode)"
            overall_healthy = True  # Still operational, just degraded
    else:
        status = "unhealthy"
        message = "Database unavailable - system not operational"
        overall_healthy = False

    return {
        "healthy": overall_healthy,
        "status": status,
        "message": message,
        "components": components,
    }


def format_health_response(health: dict[str, Any]) -> str:
    """Format health check results as human-readable string.

    Args:
        health: Health check dictionary

    Returns:
        Formatted health status string
    """
    lines = [
        f"System Health: {health['status'].upper()}",
        f"Message: {health['message']}",
        "",
        "Components:",
    ]

    for component_name, component_health in health.get("components", {}).items():
        status_symbol = "✓" if component_health.get("healthy") else "✗"
        lines.append(
            f"  {status_symbol} {component_name.title()}: {component_health.get('message', 'Unknown')}"
        )

        # Add details if available
        details = component_health.get("details", {})
        if details:
            for key, value in details.items():
                if key != "error":  # Skip error details in summary
                    lines.append(f"      {key}: {value}")

    return "\n".join(lines)
