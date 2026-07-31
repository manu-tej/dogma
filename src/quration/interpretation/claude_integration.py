"""
Claude tool calling integration for LLM interpretation.

This module provides integration with Anthropic's Claude API for
tool-augmented interpretation of bioinformatics data.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from quration.config import get_config
from quration.interpretation.executor import ToolExecutor, create_executor
from quration.interpretation.models import (
    InterpretationResult,
    InterpretationType,
    ToolCallRecord,
    ToolCallStatus,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """A message in a conversation."""

    role: Literal["user", "assistant"] = Field(description="Message role")
    content: str | list[dict[str, Any]] = Field(description="Message content")


class ToolUseBlock(BaseModel):
    """A tool use request from Claude."""

    id: str = Field(description="Tool use ID")
    name: str = Field(description="Tool name")
    input: dict[str, Any] = Field(description="Tool input parameters")


class ToolResultBlock(BaseModel):
    """A tool result to send back to Claude."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = Field(description="ID of the tool use this responds to")
    content: str = Field(description="Tool result as string")
    is_error: bool = Field(default=False, description="Whether this is an error result")


@dataclass
class ConversationState:
    """State for a tool-augmented conversation."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    iteration_count: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)


class ClaudeToolCaller:
    """Integration with Claude API for tool-augmented interpretation.

    This class handles:
    - Claude API calls with tool definitions
    - Tool call execution and result handling
    - Conversation loop management
    - Token tracking and limits

    Example:
        ```python
        caller = ClaudeToolCaller()

        result = await caller.interpret(
            prompt="Analyze the role of TP53 in cancer based on...",
            system_prompt="You are a bioinformatics expert...",
            max_iterations=10,
        )
        ```
    """

    def __init__(
        self,
        executor: ToolExecutor | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ):
        """Initialize the Claude tool caller.

        Args:
            executor: Tool executor (creates default if not provided)
            model: Claude model to use (defaults to config)
            max_tokens: Maximum tokens per response
            temperature: Response temperature
        """
        self._executor = executor or create_executor()
        self._client: Any = None

        # Get config
        config = get_config().interpretation
        self._model = model or config.default_model
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def _get_client(self) -> Any:
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                # Get API key from config
                llm_config = get_config().llm
                api_key = llm_config.anthropic.api_key

                self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
        return self._client

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions in Anthropic format."""
        return self._executor.get_tool_definitions()

    async def _execute_tool(
        self, tool_use: ToolUseBlock
    ) -> tuple[ToolResultBlock, ToolCallRecord]:
        """Execute a tool and return the result.

        Args:
            tool_use: Tool use request from Claude

        Returns:
            Tuple of (result block, call record)
        """
        result, record = await self._executor.execute_with_record(
            tool_use.name, **tool_use.input
        )

        if result.success:
            content = json.dumps(result.data, default=str)
            is_error = False
        else:
            content = f"Error: {result.error}"
            is_error = True

        result_block = ToolResultBlock(
            tool_use_id=tool_use.id,
            content=content,
            is_error=is_error,
        )

        return result_block, record

    def _parse_tool_uses(
        self, content_blocks: list[dict[str, Any]]
    ) -> list[ToolUseBlock]:
        """Parse tool use blocks from response content.

        Args:
            content_blocks: Response content blocks

        Returns:
            List of tool use requests
        """
        tool_uses = []
        for block in content_blocks:
            if block.get("type") == "tool_use":
                tool_uses.append(
                    ToolUseBlock(
                        id=block["id"],
                        name=block["name"],
                        input=block.get("input", {}),
                    )
                )
        return tool_uses

    def _extract_text(self, content_blocks: list[dict[str, Any]]) -> str:
        """Extract text content from response blocks.

        Args:
            content_blocks: Response content blocks

        Returns:
            Concatenated text content
        """
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)

    async def interpret(
        self,
        prompt: str,
        interpretation_type: InterpretationType,
        system_prompt: str | None = None,
        max_iterations: int = 10,
        context: dict[str, Any] | None = None,
    ) -> InterpretationResult:
        """Run tool-augmented interpretation.

        Args:
            prompt: User prompt for interpretation
            interpretation_type: Type of interpretation being performed
            system_prompt: System prompt (optional)
            max_iterations: Maximum tool calling iterations
            context: Additional context data

        Returns:
            InterpretationResult with interpretation and tool calls
        """
        client = await self._get_client()
        state = ConversationState()

        # Build system prompt
        if system_prompt is None:
            system_prompt = self._default_system_prompt()

        # Add context to prompt if provided
        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2, default=str)
            full_prompt = f"{prompt}\n\nContext data:\n```json\n{context_str}\n```"

        # Initialize conversation
        state.messages.append({"role": "user", "content": full_prompt})

        # Get tools
        tools = self._get_tool_definitions()

        final_text = ""
        all_text_blocks: list[str] = []
        stop_reason = ""

        try:
            while state.iteration_count < max_iterations:
                state.iteration_count += 1

                # Call Claude
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    system=system_prompt,
                    tools=tools,
                    messages=state.messages,
                )

                # Track tokens
                state.total_input_tokens += response.usage.input_tokens
                state.total_output_tokens += response.usage.output_tokens

                stop_reason = response.stop_reason

                # Parse response
                content_blocks = [
                    block.model_dump() for block in response.content
                ]

                # Extract any text
                text = self._extract_text(content_blocks)
                if text:
                    all_text_blocks.append(text)
                    final_text = text

                # Check if done
                if stop_reason == "end_turn":
                    break

                # Parse tool uses
                tool_uses = self._parse_tool_uses(content_blocks)

                if not tool_uses:
                    # No more tool calls, we're done
                    break

                # Add assistant message
                state.messages.append(
                    {"role": "assistant", "content": content_blocks}
                )

                # Execute tools and collect results
                tool_results = []
                for tool_use in tool_uses:
                    result_block, record = await self._execute_tool(tool_use)
                    tool_results.append(result_block.model_dump())
                    state.tool_calls.append(record)

                # Add tool results
                state.messages.append(
                    {"role": "user", "content": tool_results}
                )

            # If the final text looks like a preamble rather than actual
            # analysis, nudge the model to produce the real content
            _PREAMBLE_MARKERS = [
                "let me compile",
                "let me provide",
                "now i have",
                "now let me",
                "i'll compile",
                "i'll provide",
                "let me analyze",
                "i'll analyze",
                "comprehensive analysis:",
                "detailed analysis:",
            ]
            if (
                len(final_text) < 300
                and state.iteration_count < max_iterations
                and any(
                    marker in final_text.lower()
                    for marker in _PREAMBLE_MARKERS
                )
            ):
                # Add the preamble as assistant message, then nudge
                state.messages.append(
                    {"role": "assistant", "content": [{"type": "text", "text": final_text}]}
                )
                state.messages.append(
                    {"role": "user", "content": "Please write the complete analysis now. Do not use any more tools — just provide the full written interpretation based on all the information you've gathered."}
                )
                state.iteration_count += 1
                nudge_response = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    system=system_prompt,
                    messages=state.messages,
                )
                state.total_input_tokens += nudge_response.usage.input_tokens
                state.total_output_tokens += nudge_response.usage.output_tokens
                nudge_blocks = [b.model_dump() for b in nudge_response.content]
                nudge_text = self._extract_text(nudge_blocks)
                if nudge_text and len(nudge_text) > len(final_text):
                    final_text = nudge_text
                    all_text_blocks.append(nudge_text)

            # Use the longest text block if the final one is still short
            best_text = final_text
            if len(all_text_blocks) > 1 and len(final_text) < 200:
                longest = max(all_text_blocks, key=len)
                if len(longest) > len(final_text):
                    best_text = longest

            duration_seconds = (
                datetime.utcnow() - state.start_time
            ).total_seconds()

            return InterpretationResult(
                interpretation_type=interpretation_type,
                summary=best_text,
                claims=[],  # Claims extraction handled separately
                tool_calls=state.tool_calls,
                token_usage=TokenUsage(
                    input_tokens=state.total_input_tokens,
                    output_tokens=state.total_output_tokens,
                    total_tokens=state.total_input_tokens
                    + state.total_output_tokens,
                ),
                model_used=self._model,
                confidence_score=0.7,  # Default confidence, can be refined later
                processing_time_ms=duration_seconds * 1000,
                metadata={
                    "iterations": state.iteration_count,
                    "stop_reason": stop_reason,
                    "tool_count": len(state.tool_calls),
                },
            )

        except Exception as e:
            logger.exception(f"Interpretation error: {e}")
            duration_seconds = (
                datetime.utcnow() - state.start_time
            ).total_seconds()

            return InterpretationResult(
                interpretation_type=interpretation_type,
                summary=f"Error during interpretation: {e}",
                # Declared field, not `metadata`. The cause used to be passed as
                # `metadata={"error": ...}`, which this model does not declare,
                # so pydantic dropped it and left the reason readable only by
                # parsing the summary prose. Consumers check `.failed`.
                error=str(e),
                claims=[],
                tool_calls=state.tool_calls,
                token_usage=TokenUsage(
                    input_tokens=state.total_input_tokens,
                    output_tokens=state.total_output_tokens,
                    total_tokens=state.total_input_tokens
                    + state.total_output_tokens,
                ),
                model_used=self._model,
                confidence_score=0.0,  # Low confidence due to error
                processing_time_ms=duration_seconds * 1000,
                metadata={
                    "error": str(e),
                    "iterations": state.iteration_count,
                },
            )

    async def single_tool_call(
        self,
        prompt: str,
        tool_name: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Make a single focused tool call.

        Useful for simple queries where you know which tool to use.

        Args:
            prompt: User prompt
            tool_name: Name of the tool to use
            system_prompt: Optional system prompt

        Returns:
            Tool result data
        """
        client = await self._get_client()

        # Get specific tool definition
        all_tools = self._get_tool_definitions()
        tools = [t for t in all_tools if t["name"] == tool_name]

        if not tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        if system_prompt is None:
            system_prompt = (
                f"You are an assistant that uses the {tool_name} tool to answer questions. "
                f"Always use the tool to get accurate information."
            )

        response = await client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system_prompt,
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse tool use
        content_blocks = [block.model_dump() for block in response.content]
        tool_uses = self._parse_tool_uses(content_blocks)

        if not tool_uses:
            raise ValueError("No tool call was made")

        # Execute the tool
        tool_use = tool_uses[0]
        result, _ = await self._executor.execute_with_record(
            tool_use.name, **tool_use.input
        )

        if result.success:
            return result.data or {}
        else:
            raise RuntimeError(f"Tool execution failed: {result.error}")

    def _default_system_prompt(self) -> str:
        """Get the default system prompt for interpretation."""
        return """You are an expert bioinformatics analyst interpreting gene expression and omics data.

Your task is to provide scientifically accurate interpretations by:
1. Using the available tools to gather evidence from databases
2. Grounding all claims in tool results and literature
3. Clearly stating confidence levels for interpretations
4. Acknowledging limitations and uncertainties

When analyzing differentially expressed genes (DEGs):
- Look up gene functions and pathways
- Search for relevant literature
- Consider protein interactions
- Identify enriched biological processes

Always cite your sources and be precise about what the evidence supports vs. what is speculation."""

    def list_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool names
        """
        return self._executor.list_tools()

    def get_executor_metrics(self) -> dict[str, Any]:
        """Get tool executor metrics.

        Returns:
            Execution metrics
        """
        return self._executor.get_metrics()


class StreamingClaudeToolCaller(ClaudeToolCaller):
    """Claude tool caller with streaming support.

    Provides the same functionality as ClaudeToolCaller but with
    streaming responses for real-time output.
    """

    async def interpret_streaming(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_iterations: int = 10,
        context: dict[str, Any] | None = None,
    ):
        """Run tool-augmented interpretation with streaming.

        Yields text chunks as they are generated.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            max_iterations: Maximum iterations
            context: Additional context

        Yields:
            Text chunks from Claude's response
        """
        client = await self._get_client()
        state = ConversationState()

        if system_prompt is None:
            system_prompt = self._default_system_prompt()

        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2, default=str)
            full_prompt = f"{prompt}\n\nContext data:\n```json\n{context_str}\n```"

        state.messages.append({"role": "user", "content": full_prompt})
        tools = self._get_tool_definitions()

        while state.iteration_count < max_iterations:
            state.iteration_count += 1

            # Stream response
            collected_content = []
            tool_uses = []

            async with client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system_prompt,
                tools=tools,
                messages=state.messages,
            ) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                yield delta.text

                # Get final message
                response = await stream.get_final_message()

            # Track tokens
            state.total_input_tokens += response.usage.input_tokens
            state.total_output_tokens += response.usage.output_tokens

            stop_reason = response.stop_reason
            content_blocks = [block.model_dump() for block in response.content]

            if stop_reason == "end_turn":
                break

            tool_uses = self._parse_tool_uses(content_blocks)
            if not tool_uses:
                break

            # Add assistant message and execute tools
            state.messages.append({"role": "assistant", "content": content_blocks})

            tool_results = []
            for tool_use in tool_uses:
                yield f"\n[Calling tool: {tool_use.name}...]\n"
                result_block, record = await self._execute_tool(tool_use)
                tool_results.append(result_block.model_dump())
                state.tool_calls.append(record)
                yield f"[Tool {tool_use.name} complete]\n"

            state.messages.append({"role": "user", "content": tool_results})


# Factory functions
def create_claude_caller(
    include_all_tools: bool = True,
    model: str | None = None,
) -> ClaudeToolCaller:
    """Create a Claude tool caller with all tools registered.

    Args:
        include_all_tools: Register all available tools
        model: Model to use (optional)

    Returns:
        Configured ClaudeToolCaller
    """
    executor = create_executor(include_all_tools=include_all_tools)
    return ClaudeToolCaller(executor=executor, model=model)


def create_streaming_caller(
    include_all_tools: bool = True,
    model: str | None = None,
) -> StreamingClaudeToolCaller:
    """Create a streaming Claude tool caller.

    Args:
        include_all_tools: Register all available tools
        model: Model to use (optional)

    Returns:
        Configured StreamingClaudeToolCaller
    """
    executor = create_executor(include_all_tools=include_all_tools)
    return StreamingClaudeToolCaller(executor=executor, model=model)
