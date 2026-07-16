"""LLM provider abstraction supporting Anthropic and OpenRouter."""

import logging
import os
import time
from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

import anthropic
import requests

# Optional raw-LLM-capture hook. When an outer caller sets this contextvar to a
# list, every provider's ``create_message`` appends a best-effort record of the
# exact prompt/system/response for that call. Default ``None`` is a zero-cost
# no-op: no list, nothing captured, no call site or return type changes.
llm_capture_var: ContextVar[Optional[list]] = ContextVar("llm_capture", default=None)

# Import observability components (lazy import to avoid circular dependencies)
try:
    from quration.observability import get_langfuse_client, get_metrics
    from quration.observability.structured_logger import get_trace_id
except ImportError:
    get_langfuse_client = None  # type: ignore
    get_metrics = None  # type: ignore
    get_trace_id = None  # type: ignore

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Create a message and return the text response."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Create a message using Anthropic API with observability tracking."""
        # Get observability components
        langfuse_client = get_langfuse_client() if get_langfuse_client else None
        metrics = get_metrics() if get_metrics else None
        trace_id = get_trace_id() if get_trace_id else None

        # Start timing
        start_time = time.time()
        status = "success"
        error: Optional[Exception] = None

        # Prepare message kwargs
        message_kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system:
            message_kwargs["system"] = system

        # Add any additional kwargs (e.g., system cache control)
        message_kwargs.update(kwargs)

        try:
            # Call Anthropic API
            message = self.client.messages.create(**message_kwargs)
            response_text = message.content[0].text

            # Calculate latency
            latency = time.time() - start_time

            # Extract token usage
            usage = message.usage
            tokens = {
                "input": usage.input_tokens,
                "output": usage.output_tokens,
            }

            # Add cache tokens if available
            if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
                tokens["cache_read"] = usage.cache_read_input_tokens
            if hasattr(usage, "cache_creation_input_tokens") and usage.cache_creation_input_tokens:
                tokens["cache_write"] = usage.cache_creation_input_tokens

            # Calculate cost (Anthropic pricing as of 2025)
            cost = self._calculate_cost(model, tokens)

            # Check if cache was hit
            cache_hit = tokens.get("cache_read", 0) > 0

            # Track in LangFuse
            if langfuse_client and langfuse_client.enabled and trace_id:
                # Format prompt for LangFuse
                prompt_parts = []
                if system:
                    prompt_parts.append(f"System: {system}")
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join([
                            block.get("text", "") for block in content
                            if isinstance(block, dict) and block.get("type") == "text"
                        ])
                    prompt_parts.append(f"{role.capitalize()}: {content}")
                prompt_text = "\n\n".join(prompt_parts)

                langfuse_client.create_generation(
                    trace_id=trace_id,
                    name="Anthropic Claude Generation",
                    model=model,
                    prompt=prompt_text,
                    completion=response_text,
                    usage=tokens,
                    metadata={
                        "provider": "anthropic",
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "cache_hit": cache_hit,
                        "cost_usd": cost,
                        **kwargs,
                    },
                )

            # Record metrics
            if metrics and metrics._enabled:
                metrics.record_llm_request(
                    model=model,
                    provider="anthropic",
                    status=status,
                    latency=latency,
                    tokens=tokens,
                    cost=cost,
                    cache_hit=cache_hit,
                )

            # Log completion
            logger.info(
                f"Anthropic API call completed: model={model}, tokens={tokens}, cost=${cost:.4f}, latency={latency:.2f}s"
            )

            # Best-effort raw-LLM capture (no-op unless a buffer is active).
            _buf = llm_capture_var.get()
            if _buf is not None:
                try:
                    import json as _json

                    _buf.append({
                        "provider": "anthropic",
                        "model": model,
                        "system": system,
                        "prompt": _json.dumps(messages, default=str),
                        "response": response_text,
                    })
                except Exception:
                    pass

            return response_text

        except Exception as e:
            status = "error"
            error = e
            latency = time.time() - start_time

            # Record error metrics
            if metrics and metrics._enabled:
                metrics.record_llm_request(
                    model=model,
                    provider="anthropic",
                    status=status,
                    latency=latency,
                )
                metrics.record_error(
                    component="llm_provider",
                    error_type=type(e).__name__,
                )

            logger.error(
                f"Anthropic API call failed: model={model}, error={str(e)}",
                exc_info=True,
            )
            raise

    def _calculate_cost(self, model: str, tokens: Dict[str, int]) -> float:
        """Calculate cost based on token usage and model pricing.

        Pricing as of January 2025 (per million tokens):
        Claude Haiku 4.5: $0.25 input, $1.25 output, $0.30 cache write, $0.03 cache read
        Claude Sonnet 4.5: $3.00 input, $15.00 output, $3.75 cache write, $0.30 cache read
        Claude Opus 4: $15.00 input, $75.00 output, $18.75 cache write, $1.50 cache read

        Args:
            model: Model name
            tokens: Token usage dict

        Returns:
            Cost in USD
        """
        # Define pricing per million tokens
        pricing = {
            "claude-haiku-4": {
                "input": 0.25,
                "output": 1.25,
                "cache_write": 0.30,
                "cache_read": 0.03,
            },
            "claude-sonnet-4": {
                "input": 3.00,
                "output": 15.00,
                "cache_write": 3.75,
                "cache_read": 0.30,
            },
            "claude-opus-4": {
                "input": 15.00,
                "output": 75.00,
                "cache_write": 18.75,
                "cache_read": 1.50,
            },
        }

        # Determine model family
        model_family = None
        for family in pricing.keys():
            if family in model.lower():
                model_family = family
                break

        if not model_family:
            # Default to Sonnet pricing if unknown
            model_family = "claude-sonnet-4"

        prices = pricing[model_family]

        # Calculate cost
        cost = 0.0
        cost += tokens.get("input", 0) * prices["input"] / 1_000_000
        cost += tokens.get("output", 0) * prices["output"] / 1_000_000
        cost += tokens.get("cache_write", 0) * prices["cache_write"] / 1_000_000
        cost += tokens.get("cache_read", 0) * prices["cache_read"] / 1_000_000

        return cost


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider (OpenAI-compatible API)."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        self.site_url = site_url or os.environ.get("OPENROUTER_SITE_URL", "")
        self.app_name = app_name or os.environ.get("OPENROUTER_APP_NAME", "quration")

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Create a message using OpenRouter API (OpenAI-compatible) with observability tracking."""
        # Get observability components
        langfuse_client = get_langfuse_client() if get_langfuse_client else None
        metrics = get_metrics() if get_metrics else None
        trace_id = get_trace_id() if get_trace_id else None

        # Start timing
        start_time = time.time()
        status = "success"

        # Convert Anthropic-style messages to OpenAI format if needed
        openai_messages = []

        if system:
            openai_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            # Handle Anthropic's content format
            if isinstance(content, list):
                # Extract text from Anthropic's content blocks
                text_content = ""
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif isinstance(block, str):
                        text_content += block
                content = text_content

            openai_messages.append({"role": role, "content": content})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        payload = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            response.raise_for_status()
            result = response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                raise ValueError(f"Unexpected OpenRouter response: {result}")

            response_text = result["choices"][0]["message"]["content"]

            # Calculate latency
            latency = time.time() - start_time

            # Extract token usage if available
            tokens = {}
            cost = 0.0
            if "usage" in result:
                usage = result["usage"]
                tokens = {
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                }
                # Estimate cost (OpenRouter typically charges similar to native API)
                cost = self._estimate_cost(model, tokens)

            # Track in LangFuse
            if langfuse_client and langfuse_client.enabled and trace_id:
                # Format prompt
                prompt_text = "\n\n".join([
                    f"{msg['role'].capitalize()}: {msg['content']}"
                    for msg in openai_messages
                ])

                langfuse_client.create_generation(
                    trace_id=trace_id,
                    name="OpenRouter Generation",
                    model=model,
                    prompt=prompt_text,
                    completion=response_text,
                    usage=tokens,
                    metadata={
                        "provider": "openrouter",
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "cost_usd": cost,
                        **kwargs,
                    },
                )

            # Record metrics
            if metrics and metrics._enabled:
                metrics.record_llm_request(
                    model=model,
                    provider="openrouter",
                    status=status,
                    latency=latency,
                    tokens=tokens if tokens else None,
                    cost=cost if cost > 0 else None,
                    cache_hit=False,
                )

            # Log completion
            logger.info(
                f"OpenRouter API call completed: model={model}, tokens={tokens}, cost=${cost:.4f}, latency={latency:.2f}s"
            )

            # Best-effort raw-LLM capture (no-op unless a buffer is active).
            _buf = llm_capture_var.get()
            if _buf is not None:
                try:
                    import json as _json

                    _buf.append({
                        "provider": "openrouter",
                        "model": model,
                        "system": system or "",
                        "prompt": _json.dumps(openai_messages, default=str),
                        "response": response_text,
                    })
                except Exception:
                    pass

            return response_text

        except Exception as e:
            status = "error"
            latency = time.time() - start_time

            # Record error metrics
            if metrics and metrics._enabled:
                metrics.record_llm_request(
                    model=model,
                    provider="openrouter",
                    status=status,
                    latency=latency,
                )
                metrics.record_error(
                    component="llm_provider",
                    error_type=type(e).__name__,
                )

            logger.error(
                f"OpenRouter API call failed: model={model}, error={str(e)}",
                exc_info=True,
            )
            raise

    def _estimate_cost(self, model: str, tokens: Dict[str, int]) -> float:
        """Estimate cost for OpenRouter (uses similar pricing to native APIs).

        Args:
            model: Model name
            tokens: Token usage dict

        Returns:
            Estimated cost in USD
        """
        # OpenRouter pricing is similar to native APIs with a small markup
        # Using approximate Claude pricing
        if "haiku" in model.lower():
            input_price = 0.25 / 1_000_000
            output_price = 1.25 / 1_000_000
        elif "opus" in model.lower():
            input_price = 15.00 / 1_000_000
            output_price = 75.00 / 1_000_000
        else:  # Sonnet or unknown
            input_price = 3.00 / 1_000_000
            output_price = 15.00 / 1_000_000

        cost = (
            tokens.get("input", 0) * input_price +
            tokens.get("output", 0) * output_price
        )
        return cost


def _content_to_text(content: Any) -> str:
    """Flatten Anthropic-style message/system content into plain text.

    Handles a bare string, or a list of content blocks (dicts with a
    ``text`` field, as used for cache-control system blocks). Non-text
    blocks (images, tool calls) are skipped — the subscription CLI path is
    a text-only completion.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return str(content)


class ClaudeSubscriptionProvider(LLMProvider):
    """LLM provider backed by the headless ``claude -p`` CLI.

    Uses the locally logged-in Claude Code (Pro/Max) subscription OAuth
    instead of a metered API key. Each ``create_message`` call shells out to
    a single-shot, tool-free ``claude -p`` invocation and returns the
    assistant text.

    **Local, single-operator use only.** Anthropic prohibits using
    subscription auth to back a shared/deployed product. For any self-serve
    or multi-user demo, use :class:`AnthropicProvider` with an API key.
    """

    # CLI accepts the bare family aliases; map full dated model IDs onto them.
    _ALIAS_BY_FAMILY = (("haiku", "haiku"), ("opus", "opus"), ("sonnet", "sonnet"))

    def __init__(
        self,
        claude_executable: str = "claude",
        force_subscription: bool = True,
        timeout_seconds: int = 180,
        working_dir: Optional[str] = None,
    ):
        import tempfile

        self.claude_executable = claude_executable
        self.force_subscription = force_subscription
        self.timeout_seconds = timeout_seconds
        # Run in a neutral dir so the CLI doesn't load the host project's
        # CLAUDE.md / repo context into every completion.
        self.working_dir = working_dir or tempfile.gettempdir()

    def _model_alias(self, model: str) -> str:
        lowered = (model or "").lower()
        for family, alias in self._ALIAS_BY_FAMILY:
            if family in lowered:
                return alias
        # Already an alias or an exact ID the CLI understands — pass through.
        return model or "sonnet"

    def create_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Run a one-shot ``claude -p`` completion and return the text.

        Note: ``max_tokens`` and ``temperature`` are accepted for interface
        compatibility but not forwarded — the headless CLI manages those.
        """
        import json
        import shutil
        import subprocess

        metrics = get_metrics() if get_metrics else None
        start_time = time.time()

        # Flatten the conversation into a single prompt for stdin (avoids
        # ARG_MAX limits on large curation prompts).
        prompt_parts = []
        for msg in messages:
            role = (msg.get("role") or "user").capitalize()
            text = _content_to_text(msg.get("content"))
            if text:
                prompt_parts.append(f"{role}: {text}" if len(messages) > 1 else text)
        prompt = "\n\n".join(prompt_parts)

        system_text = _content_to_text(system) if system else ""

        cmd = [
            self.claude_executable,
            "-p",
            "--output-format", "json",
            "--tools", "",  # pure completion: no file/bash/agentic tools
            "--no-session-persistence",
            "--model", self._model_alias(model),
        ]
        if system_text:
            # Override (not append) so the coding-agent default prompt does
            # not leak into the app's responses.
            cmd += ["--system-prompt", system_text]

        # Force subscription OAuth: a stray ANTHROPIC_API_KEY would otherwise
        # silently switch the CLI to metered billing.
        env = dict(os.environ)
        if self.force_subscription:
            env.pop("ANTHROPIC_API_KEY", None)

        if shutil.which(self.claude_executable) is None and not os.path.isabs(
            self.claude_executable
        ):
            raise RuntimeError(
                f"Claude CLI '{self.claude_executable}' not found on PATH. "
                "Install Claude Code and run `claude login`, or set "
                "claude_subscription.claude_executable / CLAUDE_CLI_PATH."
            )

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                env=env,
                cwd=self.working_dir,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            self._record_error(metrics, model, start_time, "TimeoutExpired")
            raise RuntimeError(
                f"claude -p timed out after {self.timeout_seconds}s"
            ) from e

        if result.returncode != 0:
            self._record_error(metrics, model, start_time, "NonZeroExit")
            raise RuntimeError(
                f"claude -p exited {result.returncode}: "
                f"{(result.stderr or result.stdout or '').strip()[:500]}"
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self._record_error(metrics, model, start_time, "JSONDecodeError")
            raise RuntimeError(
                f"claude -p returned non-JSON output: {result.stdout[:500]}"
            ) from e

        if payload.get("is_error"):
            self._record_error(metrics, model, start_time, "ClaudeError")
            raise RuntimeError(
                f"claude -p reported an error: {payload.get('result') or payload}"
            )

        response_text = payload.get("result", "")
        latency = time.time() - start_time

        usage_raw = payload.get("usage") or {}
        tokens = {
            "input": usage_raw.get("input_tokens", 0),
            "output": usage_raw.get("output_tokens", 0),
        }
        if metrics and getattr(metrics, "_enabled", False):
            metrics.record_llm_request(
                model=model,
                provider="claude_subscription",
                status="success",
                latency=latency,
                tokens=tokens,
                cost=0.0,  # billed against the subscription, not metered
                cache_hit=bool(usage_raw.get("cache_read_input_tokens")),
            )

        logger.info(
            "claude -p completed: model=%s alias=%s tokens=%s latency=%.2fs",
            model, self._model_alias(model), tokens, latency,
        )

        # Best-effort raw-LLM capture (no-op unless a buffer is active).
        _buf = llm_capture_var.get()
        if _buf is not None:
            try:
                _buf.append({
                    "provider": "claude_subscription",
                    "model": model,
                    "system": system_text,
                    "prompt": prompt,
                    "response": response_text,
                })
            except Exception:
                pass

        return response_text

    @staticmethod
    def _record_error(metrics, model, start_time, error_type):
        if metrics and getattr(metrics, "_enabled", False):
            metrics.record_llm_request(
                model=model,
                provider="claude_subscription",
                status="error",
                latency=time.time() - start_time,
            )
            metrics.record_error(component="llm_provider", error_type=error_type)


def get_llm_provider(
    provider_name: str = "anthropic",
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> LLMProvider:
    """
    Factory function to get an LLM provider.

    Args:
        provider_name: Name of the provider ("anthropic" or "openrouter")
        api_key: API key for the provider (optional, falls back to env vars)
        **kwargs: Additional provider-specific arguments

    Returns:
        LLMProvider instance

    Example:
        >>> provider = get_llm_provider("anthropic")
        >>> response = provider.create_message(
        ...     messages=[{"role": "user", "content": "Hello!"}],
        ...     model="claude-3-5-sonnet-20241022"
        ... )
    """
    if provider_name.lower() == "anthropic":
        return AnthropicProvider(api_key=api_key)
    elif provider_name.lower() == "openrouter":
        return OpenRouterProvider(
            api_key=api_key,
            site_url=kwargs.get("site_url"),
            app_name=kwargs.get("app_name"),
        )
    elif provider_name.lower() == "claude_subscription":
        return ClaudeSubscriptionProvider(
            claude_executable=kwargs.get("claude_executable", "claude"),
            force_subscription=kwargs.get("force_subscription", True),
            timeout_seconds=kwargs.get("timeout_seconds", 180),
        )
    else:
        raise ValueError(
            f"Unknown provider: {provider_name}. Supported: 'anthropic', "
            "'openrouter', 'claude_subscription'"
        )


def get_provider_from_config(config: Any = None) -> LLMProvider:
    """Build an :class:`LLMProvider` honoring ``config.llm.provider``.

    This is the single entry point call sites should use so that switching
    ``provider`` in config (e.g. to ``claude_subscription`` for local,
    subscription-backed runs) actually takes effect everywhere.
    """
    if config is None:
        from quration.config import get_config

        config = get_config()

    llm = config.llm
    name = (llm.provider or "anthropic").lower()

    if name == "openrouter":
        oc = llm.openrouter
        return get_llm_provider(
            "openrouter",
            api_key=oc.api_key or None,
            site_url=oc.site_url,
            app_name=oc.app_name,
        )
    if name == "claude_subscription":
        cs = llm.claude_subscription
        return get_llm_provider(
            "claude_subscription",
            claude_executable=cs.claude_executable,
            force_subscription=cs.force_subscription,
            timeout_seconds=cs.timeout_seconds,
        )
    return get_llm_provider("anthropic", api_key=llm.anthropic.api_key or None)


def get_model_for_config(config: Any = None, tier: str = "smart") -> str:
    """Return the model string for the active provider and tier.

    ``tier`` is ``"smart"`` or ``"fast"``. For ``claude_subscription`` the
    values are CLI aliases (``sonnet``/``haiku``); for ``anthropic`` they are
    full model IDs — the subscription provider maps either onto an alias.
    """
    if config is None:
        from quration.config import get_config

        config = get_config()

    llm = config.llm
    name = (llm.provider or "anthropic").lower()
    if name == "openrouter":
        pc = llm.openrouter
    elif name == "claude_subscription":
        pc = llm.claude_subscription
    else:
        pc = llm.anthropic
    return pc.fast_model if tier == "fast" else pc.smart_model
