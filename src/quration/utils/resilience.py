"""Resilience utilities for error recovery and fault tolerance.

This module provides utilities for building resilient systems:
- Retry decorators with exponential backoff
- Circuit breaker pattern implementation
- Jitter for avoiding thundering herd
- Configurable failure thresholds
"""

import logging
import random
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast, not attempting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before entering HALF_OPEN state
        success_threshold: Successes needed in HALF_OPEN to close circuit
        name: Identifier for this circuit breaker
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
        name: str = "default",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Failures needed to open circuit (default: 5)
            recovery_timeout: Seconds before trying HALF_OPEN (default: 30)
            success_threshold: Successes in HALF_OPEN to close (default: 2)
            name: Circuit breaker identifier
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0

        return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self._last_failure_time is None:
            return True

        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by func
        """
        current_state = self.state

        # Fail fast if circuit is open
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Waiting for recovery timeout ({self.recovery_timeout}s)"
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info(
                    f"Circuit breaker '{self.name}' closing after "
                    f"{self._success_count} successful attempts"
                )
                self._close()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success in CLOSED state
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(
                f"Circuit breaker '{self.name}' failed during HALF_OPEN, "
                "returning to OPEN state"
            )
            self._open()
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker '{self.name}' opening after "
                    f"{self._failure_count} failures"
                )
                self._open()

    def _open(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._success_count = 0

    def _close(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")
        self._close()
        self._last_failure_time = None

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics.

        Returns:
            Dictionary with current state and counters
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }


def retry_on_failure(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 10.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    reraise: bool = True,
) -> Callable[[F], F]:
    """Decorator for retrying functions with exponential backoff and jitter.

    This decorator uses tenacity to retry failed function calls with
    exponential backoff and random jitter to avoid thundering herd.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds (default: 2.0)
        max_wait: Maximum wait time in seconds (default: 10.0)
        exceptions: Tuple of exception types to retry (default: all)
        reraise: Re-raise exception after all retries (default: True)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_on_failure(max_attempts=3, min_wait=1.0, max_wait=5.0)
        async def fetch_data():
            # This will retry up to 3 times on failure
            return await db.query()
    """

    def decorator(func: F) -> F:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait)
            + wait_random(0, 1),  # Add jitter
            retry=retry_if_exception_type(exceptions),
            reraise=reraise,
            before_sleep=lambda retry_state: logger.warning(
                f"Retry attempt {retry_state.attempt_number}/{max_attempts} "
                f"for {func.__name__} after error: {retry_state.outcome.exception()}"
            ),
        )
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait)
            + wait_random(0, 1),  # Add jitter
            retry=retry_if_exception_type(exceptions),
            reraise=reraise,
            before_sleep=lambda retry_state: logger.warning(
                f"Retry attempt {retry_state.attempt_number}/{max_attempts} "
                f"for {func.__name__} after error: {retry_state.outcome.exception()}"
            ),
        )
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry.

    Retryable errors:
    - Connection errors
    - Timeout errors
    - Temporary network issues
    - Database connection pool exhaustion

    Non-retryable errors:
    - Validation errors
    - Authentication errors
    - Resource not found errors
    - Invalid input errors

    Args:
        error: Exception to check

    Returns:
        True if error is retryable, False otherwise
    """
    # Import here to avoid circular dependencies
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import TimeoutError as RedisTimeoutError
    from sqlalchemy.exc import (
        DBAPIError,
        OperationalError,
        TimeoutError as SQLTimeoutError,
    )

    # Retryable exception types
    retryable_types = (
        # Redis errors
        RedisConnectionError,
        RedisTimeoutError,
        # Database errors
        OperationalError,
        SQLTimeoutError,
        DBAPIError,
        # Network errors
        ConnectionError,
        TimeoutError,
    )

    # Check exception type
    if isinstance(error, retryable_types):
        return True

    # Check error messages for known retryable patterns
    error_message = str(error).lower()
    retryable_patterns = [
        "connection",
        "timeout",
        "temporary",
        "unavailable",
        "pool",
        "network",
    ]

    return any(pattern in error_message for pattern in retryable_patterns)


def add_jitter(value: float, max_jitter: float = 0.1) -> float:
    """Add random jitter to a value.

    Jitter helps avoid thundering herd problem where multiple
    clients retry at the same time.

    Args:
        value: Base value
        max_jitter: Maximum jitter as fraction of value (default: 10%)

    Returns:
        Value with random jitter added
    """
    jitter = value * max_jitter * (2 * random.random() - 1)
    return max(0, value + jitter)


# Global circuit breakers registry
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """Get or create a circuit breaker by name.

    This maintains a global registry of circuit breakers to ensure
    the same instance is used across the application.

    Args:
        name: Circuit breaker identifier
        failure_threshold: Failures needed to open circuit
        recovery_timeout: Seconds before trying recovery
        success_threshold: Successes needed to close circuit

    Returns:
        Circuit breaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            name=name,
        )

    return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to CLOSED state.

    Useful for testing or manual recovery operations.
    """
    for breaker in _circuit_breakers.values():
        breaker.reset()
    logger.info(f"Reset {len(_circuit_breakers)} circuit breakers")


def get_all_circuit_breaker_stats() -> list[dict[str, Any]]:
    """Get statistics for all circuit breakers.

    Returns:
        List of circuit breaker statistics dictionaries
    """
    return [breaker.get_stats() for breaker in _circuit_breakers.values()]
