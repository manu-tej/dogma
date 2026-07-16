"""
Base classes for bioinformatics tools used in LLM interpretation.

This module provides:
- ToolDefinition: Describes a tool's interface for the LLM
- BioinformaticsTool: Abstract base class for tool implementations
- ToolRegistry: Registry for managing and executing tools
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from quration.interpretation.models import ToolCallRecord, ToolCallStatus

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Base exception for tool errors."""

    pass


class ToolValidationError(ToolError):
    """Raised when tool input or output validation fails."""

    pass


class ToolDefinition(BaseModel):
    """Definition of a tool's interface for LLM consumption.

    This follows the Anthropic tool format for Claude's tool use capability.
    """

    name: str = Field(description="Unique tool name (snake_case)")
    description: str = Field(
        description="Clear description of what the tool does and when to use it"
    )
    input_schema: dict[str, Any] = Field(
        description="JSON Schema for the tool's input parameters"
    )
    output_schema: dict[str, Any] | None = Field(
        default=None, description="JSON Schema for expected output (optional)"
    )
    examples: list[dict[str, Any]] = Field(
        default_factory=list, description="Example input/output pairs"
    )
    category: str = Field(
        default="general", description="Tool category (e.g., 'gene_info', 'pathway')"
    )
    rate_limit: int | None = Field(
        default=None, description="Rate limit in requests per second"
    )
    cacheable: bool = Field(default=True, description="Whether results can be cached")
    cache_ttl_seconds: int = Field(
        default=3600, description="Cache TTL if cacheable"
    )

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format for API calls.

        Returns:
            dict: Tool definition in Anthropic's expected format
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolResult(BaseModel):
    """Result from a tool execution."""

    success: bool = Field(description="Whether the tool executed successfully")
    data: dict[str, Any] | None = Field(
        default=None, description="Result data on success"
    )
    error: str | None = Field(default=None, description="Error message on failure")
    cached: bool = Field(default=False, description="Whether result was from cache")
    latency_ms: float = Field(default=0.0, description="Execution time in milliseconds")


class BioinformaticsTool(ABC):
    """Abstract base class for bioinformatics tools.

    All tools that can be called by the LLM interpreter should inherit from
    this class and implement the required methods.

    Example:
        ```python
        class GetGeneInfoTool(BioinformaticsTool):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    name="get_gene_info",
                    description="Get information about a gene from NCBI",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "gene_symbol": {"type": "string"},
                            "organism": {"type": "string", "default": "human"}
                        },
                        "required": ["gene_symbol"]
                    }
                )

            async def execute(self, gene_symbol: str, organism: str = "human") -> dict:
                # Implementation...
                return {"gene_id": "...", "summary": "..."}
        ```
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Get the tool definition.

        Returns:
            ToolDefinition describing this tool's interface
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with the given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            dict: Tool results

        Raises:
            ToolError: If execution fails
            ToolValidationError: If input validation fails
        """
        pass

    def validate_input(self, **kwargs: Any) -> tuple[bool, list[str]]:
        """Validate input parameters against the schema.

        Args:
            **kwargs: Parameters to validate

        Returns:
            tuple: (is_valid, list of error messages)
        """
        errors = []
        schema = self.definition.input_schema

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in kwargs or kwargs[field] is None:
                errors.append(f"Missing required field: {field}")

        # Check property types (basic validation)
        properties = schema.get("properties", {})
        for key, value in kwargs.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    errors.append(
                        f"Invalid type for {key}: expected {expected_type}, "
                        f"got {type(value).__name__}"
                    )

        return len(errors) == 0, errors

    def validate_output(self, result: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate output against the schema (if defined).

        Args:
            result: Output to validate

        Returns:
            tuple: (is_valid, list of error messages)
        """
        if not self.definition.output_schema:
            return True, []

        errors = []
        schema = self.definition.output_schema

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in result:
                errors.append(f"Missing required output field: {field}")

        return len(errors) == 0, errors

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected JSON Schema type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        if expected_type not in type_mapping:
            return True  # Unknown type, assume valid

        expected = type_mapping[expected_type]
        return isinstance(value, expected)


class ToolRegistry:
    """Registry for managing and executing bioinformatics tools.

    The registry provides:
    - Tool registration and lookup
    - Async tool execution with error handling
    - Tool call recording for observability
    - Batch and parallel execution support
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, BioinformaticsTool] = {}
        self._logger = logging.getLogger(__name__)

    def register(self, tool: BioinformaticsTool) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        self._tools[name] = tool
        self._logger.info(f"Registered tool: {name}")

    def register_all(self, tools: list[BioinformaticsTool]) -> None:
        """Register multiple tools at once.

        Args:
            tools: List of tools to register
        """
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> BioinformaticsTool:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            BioinformaticsTool instance

        Raises:
            KeyError: If tool is not found
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def has(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name

        Returns:
            bool: True if tool exists
        """
        return name in self._tools

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            list: Tool names
        """
        return list(self._tools.keys())

    def get_all_definitions(self) -> list[ToolDefinition]:
        """Get definitions for all registered tools.

        Returns:
            list: Tool definitions
        """
        return [tool.definition for tool in self._tools.values()]

    def get_anthropic_tools(self) -> list[dict[str, Any]]:
        """Get all tools in Anthropic API format.

        Returns:
            list: Tools formatted for Anthropic's tool use API
        """
        return [tool.definition.to_anthropic_format() for tool in self._tools.values()]

    async def execute(
        self, name: str, validate_input: bool = True, **kwargs: Any
    ) -> ToolResult:
        """Execute a tool by name.

        Args:
            name: Tool name
            validate_input: Whether to validate input before execution
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution results
        """
        start_time = time.time()

        try:
            tool = self.get(name)

            # Validate input if requested
            if validate_input:
                is_valid, errors = tool.validate_input(**kwargs)
                if not is_valid:
                    return ToolResult(
                        success=False,
                        error=f"Input validation failed: {'; '.join(errors)}",
                        latency_ms=(time.time() - start_time) * 1000,
                    )

            # Execute the tool
            result = await tool.execute(**kwargs)

            # Validate output
            is_valid, errors = tool.validate_output(result)
            if not is_valid:
                self._logger.warning(
                    f"Tool '{name}' output validation warnings: {errors}"
                )

            latency_ms = (time.time() - start_time) * 1000
            return ToolResult(success=True, data=result, latency_ms=latency_ms)

        except ToolError as e:
            latency_ms = (time.time() - start_time) * 1000
            self._logger.error(f"Tool '{name}' error: {e}")
            return ToolResult(success=False, error=str(e), latency_ms=latency_ms)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._logger.exception(f"Unexpected error in tool '{name}'")
            return ToolResult(
                success=False, error=f"Unexpected error: {e}", latency_ms=latency_ms
            )

    async def execute_with_record(
        self, name: str, validate_input: bool = True, **kwargs: Any
    ) -> tuple[ToolResult, ToolCallRecord]:
        """Execute a tool and return both result and a record for logging.

        Args:
            name: Tool name
            validate_input: Whether to validate input
            **kwargs: Tool parameters

        Returns:
            tuple: (ToolResult, ToolCallRecord)
        """
        result = await self.execute(name, validate_input=validate_input, **kwargs)

        record = ToolCallRecord(
            tool_name=name,
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
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Args:
            calls: List of (tool_name, kwargs) tuples

        Returns:
            list: Results in the same order as input calls
        """
        tasks = [self.execute(name, **kwargs) for name, kwargs in calls]
        return await asyncio.gather(*tasks)


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry.

    Returns:
        ToolRegistry: Global registry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(tool: BioinformaticsTool) -> None:
    """Register a tool in the global registry.

    Args:
        tool: Tool to register
    """
    get_tool_registry().register(tool)
