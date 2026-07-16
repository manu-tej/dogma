"""
Tool executor with caching, rate limiting, and circuit breaker support.

This module provides an experimental executor that wraps the tool registry
with caching and resilience mechanisms for research use.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable

from quration.interpretation.models import ToolCallRecord, ToolCallStatus
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolError,
    ToolRegistry,
    ToolResult,
    get_tool_registry,
)

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for a tool."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    half_open_max_calls: int = 3

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_successes: int = 0

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_successes = 0
                return True
            return False
        else:  # HALF_OPEN
            return True

    def record_success(self) -> None:
        """Record a successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


@dataclass
class RateLimiter:
    """Token bucket rate limiter."""

    rate: float  # tokens per second
    max_tokens: float = 10.0

    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.time)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self.tokens = self.max_tokens

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Wait for a token to become available
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


@dataclass
class ExecutionMetrics:
    """Metrics for tool execution."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_calls: int = 0
    total_latency_ms: float = 0.0
    calls_by_tool: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_tool: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_calls == 0:
            return 0.0
        return self.cached_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        non_cached = self.total_calls - self.cached_calls
        if non_cached == 0:
            return 0.0
        return self.total_latency_ms / non_cached

    def record_call(
        self, tool_name: str, success: bool, cached: bool, latency_ms: float
    ) -> None:
        """Record a tool call."""
        self.total_calls += 1
        self.calls_by_tool[tool_name] += 1

        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
            self.errors_by_tool[tool_name] += 1

        if cached:
            self.cached_calls += 1
        else:
            self.total_latency_ms += latency_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "cached_calls": self.cached_calls,
            "success_rate": round(self.success_rate, 3),
            "cache_hit_rate": round(self.cache_hit_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "calls_by_tool": dict(self.calls_by_tool),
            "errors_by_tool": dict(self.errors_by_tool),
        }


class CacheEntry:
    """Cache entry with TTL."""

    def __init__(self, data: dict[str, Any], ttl_seconds: int):
        self.data = data
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class ToolExecutor:
    """Enhanced tool executor with caching, rate limiting, and circuit breakers.

    This executor wraps a ToolRegistry and provides:
    - In-memory result caching with TTL
    - Per-tool rate limiting
    - Circuit breaker pattern for failing tools
    - Execution metrics and observability
    - Retry support with backoff

    Example:
        ```python
        executor = ToolExecutor()
        executor.register_tools(create_literature_tools())

        result = await executor.execute("search_pubmed", query="TP53 cancer")

        # Get metrics
        metrics = executor.get_metrics()
        ```
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        enable_cache: bool = True,
        enable_rate_limiting: bool = True,
        enable_circuit_breaker: bool = True,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ):
        """Initialize the executor.

        Args:
            registry: Tool registry to use (defaults to global)
            enable_cache: Enable result caching
            enable_rate_limiting: Enable rate limiting
            enable_circuit_breaker: Enable circuit breaker
            max_retries: Maximum retry attempts
            retry_delay: Base delay between retries (seconds)
        """
        self._registry = registry or get_tool_registry()
        self._enable_cache = enable_cache
        self._enable_rate_limiting = enable_rate_limiting
        self._enable_circuit_breaker = enable_circuit_breaker
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Per-tool components
        self._cache: dict[str, CacheEntry] = {}
        self._rate_limiters: dict[str, RateLimiter] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Metrics
        self._metrics = ExecutionMetrics()

        # Lock for cache operations
        self._cache_lock = asyncio.Lock()

        # Hooks for extensibility
        self._pre_execute_hooks: list[Callable] = []
        self._post_execute_hooks: list[Callable] = []

    def register_tools(self, tools: list[BioinformaticsTool]) -> None:
        """Register tools and initialize their components.

        Args:
            tools: List of tools to register
        """
        for tool in tools:
            self._registry.register(tool)
            self._initialize_tool_components(tool)

    def _initialize_tool_components(self, tool: BioinformaticsTool) -> None:
        """Initialize rate limiter and circuit breaker for a tool."""
        name = tool.definition.name
        rate_limit = tool.definition.rate_limit or 10  # Default 10 req/sec

        self._rate_limiters[name] = RateLimiter(rate=rate_limit)
        self._circuit_breakers[name] = CircuitBreaker()

    def add_pre_execute_hook(self, hook: Callable) -> None:
        """Add a hook to run before tool execution.

        Hook signature: async def hook(tool_name: str, kwargs: dict) -> None
        """
        self._pre_execute_hooks.append(hook)

    def add_post_execute_hook(self, hook: Callable) -> None:
        """Add a hook to run after tool execution.

        Hook signature: async def hook(tool_name: str, result: ToolResult) -> None
        """
        self._post_execute_hooks.append(hook)

    def _generate_cache_key(self, tool_name: str, kwargs: dict[str, Any]) -> str:
        """Generate a cache key for a tool call."""
        # Sort kwargs for consistent hashing
        sorted_kwargs = json.dumps(kwargs, sort_keys=True, default=str)
        key_string = f"{tool_name}:{sorted_kwargs}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    async def _get_from_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Get a result from cache if valid."""
        if not self._enable_cache:
            return None

        async with self._cache_lock:
            entry = self._cache.get(cache_key)
            if entry and not entry.is_expired:
                return entry.data
            elif entry:
                # Clean up expired entry
                del self._cache[cache_key]
            return None

    async def _store_in_cache(
        self, cache_key: str, data: dict[str, Any], ttl_seconds: int
    ) -> None:
        """Store a result in cache."""
        if not self._enable_cache:
            return

        async with self._cache_lock:
            self._cache[cache_key] = CacheEntry(data, ttl_seconds)

    async def execute(
        self,
        tool_name: str,
        validate_input: bool = True,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool with all configured features.

        Args:
            tool_name: Name of the tool to execute
            validate_input: Whether to validate input parameters
            use_cache: Whether to use caching for this call
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution results
        """
        start_time = time.time()

        # Get tool definition for cache TTL
        try:
            tool = self._registry.get(tool_name)
            definition = tool.definition
        except KeyError:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Run pre-execute hooks
        for hook in self._pre_execute_hooks:
            try:
                await hook(tool_name, kwargs)
            except Exception as e:
                logger.warning(f"Pre-execute hook error: {e}")

        # Check cache
        cache_key = self._generate_cache_key(tool_name, kwargs)
        if use_cache and definition.cacheable:
            cached_data = await self._get_from_cache(cache_key)
            if cached_data is not None:
                latency_ms = (time.time() - start_time) * 1000
                result = ToolResult(
                    success=True, data=cached_data, cached=True, latency_ms=latency_ms
                )
                self._metrics.record_call(tool_name, True, True, latency_ms)
                return result

        # Check circuit breaker
        if self._enable_circuit_breaker:
            circuit = self._circuit_breakers.get(tool_name)
            if circuit and not circuit.can_execute():
                latency_ms = (time.time() - start_time) * 1000
                result = ToolResult(
                    success=False,
                    error=f"Circuit breaker open for tool '{tool_name}'",
                    latency_ms=latency_ms,
                )
                self._metrics.record_call(tool_name, False, False, latency_ms)
                return result

        # Apply rate limiting
        if self._enable_rate_limiting:
            rate_limiter = self._rate_limiters.get(tool_name)
            if rate_limiter:
                await rate_limiter.acquire()

        # Execute with retries
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                result = await self._registry.execute(
                    tool_name, validate_input=validate_input, **kwargs
                )

                if result.success:
                    # Update circuit breaker
                    if self._enable_circuit_breaker:
                        circuit = self._circuit_breakers.get(tool_name)
                        if circuit:
                            circuit.record_success()

                    # Store in cache
                    if use_cache and definition.cacheable and result.data:
                        await self._store_in_cache(
                            cache_key, result.data, definition.cache_ttl_seconds
                        )

                    # Record metrics
                    self._metrics.record_call(
                        tool_name, True, False, result.latency_ms
                    )

                    # Run post-execute hooks
                    for hook in self._post_execute_hooks:
                        try:
                            await hook(tool_name, result)
                        except Exception as e:
                            logger.warning(f"Post-execute hook error: {e}")

                    return result

                else:
                    last_error = result.error

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Tool '{tool_name}' attempt {attempt + 1} failed: {e}"
                )

            # Wait before retry (exponential backoff)
            if attempt < self._max_retries:
                await asyncio.sleep(self._retry_delay * (2**attempt))

        # All retries failed
        latency_ms = (time.time() - start_time) * 1000

        # Update circuit breaker
        if self._enable_circuit_breaker:
            circuit = self._circuit_breakers.get(tool_name)
            if circuit:
                circuit.record_failure()

        # Record metrics
        self._metrics.record_call(tool_name, False, False, latency_ms)

        return ToolResult(
            success=False,
            error=last_error or "Unknown error",
            latency_ms=latency_ms,
        )

    async def execute_with_record(
        self, tool_name: str, **kwargs: Any
    ) -> tuple[ToolResult, ToolCallRecord]:
        """Execute a tool and return both result and record.

        Args:
            tool_name: Tool name
            **kwargs: Tool parameters

        Returns:
            tuple: (ToolResult, ToolCallRecord)
        """
        result = await self.execute(tool_name, **kwargs)

        record = ToolCallRecord(
            tool_name=tool_name,
            tool_input=kwargs,
            tool_output=result.data,
            status=ToolCallStatus.SUCCESS if result.success else ToolCallStatus.FAILURE,
            error_message=result.error,
            latency_ms=result.latency_ms,
            cached=result.cached,
            timestamp=datetime.utcnow(),
        )

        return result, record

    async def execute_parallel(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        max_concurrent: int = 10,
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel with concurrency limit.

        Args:
            calls: List of (tool_name, kwargs) tuples
            max_concurrent: Maximum concurrent executions

        Returns:
            list: Results in the same order as input calls
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_execute(
            name: str, kwargs: dict[str, Any]
        ) -> ToolResult:
            async with semaphore:
                return await self.execute(name, **kwargs)

        tasks = [bounded_execute(name, kwargs) for name, kwargs in calls]
        return await asyncio.gather(*tasks)

    def get_metrics(self) -> dict[str, Any]:
        """Get execution metrics.

        Returns:
            dict: Metrics summary
        """
        return self._metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = ExecutionMetrics()

    def get_circuit_breaker_states(self) -> dict[str, str]:
        """Get circuit breaker states for all tools.

        Returns:
            dict: Tool name to circuit state mapping
        """
        return {
            name: breaker.state.value
            for name, breaker in self._circuit_breakers.items()
        }

    def clear_cache(self, tool_name: str | None = None) -> int:
        """Clear cache entries.

        Args:
            tool_name: Optional tool name to clear specific cache entries

        Returns:
            Number of entries cleared
        """
        if tool_name is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        # Clear entries for specific tool
        prefix = f"{tool_name}:"
        keys_to_remove = [
            k for k in self._cache.keys() if k.startswith(prefix)
        ]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in Anthropic format.

        Returns:
            list: Tool definitions for Anthropic API
        """
        return self._registry.get_anthropic_tools()

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            list: Tool names
        """
        return self._registry.list_tools()


# Factory function for creating pre-configured executor
def create_executor(
    include_all_tools: bool = True,
    enable_cache: bool = True,
    enable_rate_limiting: bool = True,
) -> ToolExecutor:
    """Create a pre-configured tool executor.

    Args:
        include_all_tools: Register all available tools
        enable_cache: Enable result caching
        enable_rate_limiting: Enable rate limiting

    Returns:
        Configured ToolExecutor
    """
    executor = ToolExecutor(
        enable_cache=enable_cache,
        enable_rate_limiting=enable_rate_limiting,
    )

    if include_all_tools:
        # Import and register all tools
        try:
            from quration.interpretation.tools.geo_tools import create_geo_tools
            from quration.interpretation.tools.kegg_tools import create_kegg_tools
            from quration.interpretation.tools.literature_tools import (
                create_literature_tools,
            )
            from quration.interpretation.tools.ncbi_gene_tools import (
                create_ncbi_gene_tools,
            )
            from quration.interpretation.tools.ontology_tools import (
                create_ontology_tools,
            )
            from quration.interpretation.tools.reactome_tools import (
                create_reactome_tools,
            )
            from quration.interpretation.tools.string_tools import (
                create_string_tools,
            )
            from quration.interpretation.tools.uniprot_tools import (
                create_uniprot_tools,
            )

            all_tools = (
                create_geo_tools()
                + create_ontology_tools()
                + create_uniprot_tools()
                + create_kegg_tools()
                + create_reactome_tools()
                + create_literature_tools()
                + create_ncbi_gene_tools()
                + create_string_tools()
            )

            executor.register_tools(all_tools)
            logger.info(f"Registered {len(all_tools)} tools in executor")

        except ImportError as e:
            logger.warning(f"Could not import all tools: {e}")

    return executor
