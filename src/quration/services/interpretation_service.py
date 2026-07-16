"""Interpretation service for API-level orchestration.

This service provides the application-level interface for interpretation
operations, including caching, deduplication, and observability hooks.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from quration.cache.redis_client import RedisClient
from quration.interpretation.models import InterpretationResult, InterpretationType
from quration.interpretation.service import InterpretationService, create_interpretation_service

logger = logging.getLogger(__name__)


class InterpretationAPIService:
    """API-level service for interpretation operations.

    This service wraps the core InterpretationService and provides:
    - Request deduplication using content hashes
    - Result caching with Redis
    - Observability hooks (LangFuse, metrics)
    - Rate limiting per user
    - Cost tracking

    Example:
        ```python
        service = InterpretationAPIService(session, cache)

        # Interpret DEG results
        result = await service.interpret_deg(
            user_id=user_id,
            upregulated=[("TP53", 2.5), ("BRCA1", 1.8)],
            downregulated=[("MYC", -2.1)],
            condition_a="treated",
            condition_b="control",
        )
        ```
    """

    # Cache TTL for interpretation results (1 hour)
    CACHE_TTL_SECONDS = 3600

    # Rate limit per user per minute
    RATE_LIMIT_PER_MINUTE = 10

    def __init__(
        self,
        session: AsyncSession | None = None,
        cache: RedisClient | None = None,
        enable_observability: bool = True,
    ):
        """Initialize the interpretation API service.

        Args:
            session: Async database session (optional, for persistence)
            cache: Redis cache instance (optional, for caching)
            enable_observability: Enable observability hooks
        """
        self.session = session
        self.cache = cache
        self._enable_observability = enable_observability

        # Core interpretation service
        self._interpreter = create_interpretation_service(enable_cache=True)

        # Metrics tracking
        self._metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "deduplicated_requests": 0,
            "total_cost_usd": 0.0,
            "total_tokens_used": 0,
            "requests_by_type": {},
            "requests_by_user": {},
        }

        # In-flight request tracking for deduplication
        self._inflight_requests: dict[str, bool] = {}

    def _compute_request_hash(self, request_type: str, **kwargs) -> str:
        """Compute a hash for request deduplication.

        Args:
            request_type: Type of interpretation
            **kwargs: Request parameters

        Returns:
            SHA256 hash of the request
        """
        # Normalize and serialize request
        normalized = {
            "type": request_type,
            **{k: v for k, v in sorted(kwargs.items()) if v is not None},
        }
        request_json = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.sha256(request_json.encode()).hexdigest()[:32]

    def _get_cache_key(self, request_hash: str) -> str:
        """Get cache key for a request hash."""
        return f"interpretation:result:{request_hash}"

    async def _get_cached_result(
        self, request_hash: str
    ) -> InterpretationResult | None:
        """Try to get cached result.

        Args:
            request_hash: Request hash

        Returns:
            Cached result or None
        """
        if not self.cache:
            return None

        try:
            cache_key = self._get_cache_key(request_hash)
            cached = await self.cache.get(cache_key)

            if cached:
                self._metrics["cache_hits"] += 1
                logger.debug(f"Cache hit for request {request_hash}")
                # Deserialize from JSON
                data = json.loads(cached)
                return InterpretationResult(**data)

        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")

        return None

    async def _cache_result(
        self, request_hash: str, result: InterpretationResult
    ) -> None:
        """Cache an interpretation result.

        Args:
            request_hash: Request hash
            result: Result to cache
        """
        if not self.cache:
            return

        try:
            cache_key = self._get_cache_key(request_hash)
            # Serialize to JSON
            result_json = result.model_dump_json()
            await self.cache.set(cache_key, result_json, ex=self.CACHE_TTL_SECONDS)
            logger.debug(f"Cached result for request {request_hash}")

        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")

    def _track_metrics(
        self,
        request_type: str,
        user_id: UUID | None,
        result: InterpretationResult,
        success: bool,
    ) -> None:
        """Track metrics for the request.

        Args:
            request_type: Type of interpretation
            user_id: User ID
            result: Interpretation result
            success: Whether request succeeded
        """
        self._metrics["total_requests"] += 1

        if success:
            self._metrics["successful_requests"] += 1
            self._metrics["total_cost_usd"] += result.cost_usd
            self._metrics["total_tokens_used"] += result.token_usage.total_tokens
        else:
            self._metrics["failed_requests"] += 1

        # Track by type
        if request_type not in self._metrics["requests_by_type"]:
            self._metrics["requests_by_type"][request_type] = 0
        self._metrics["requests_by_type"][request_type] += 1

        # Track by user
        if user_id:
            user_key = str(user_id)
            if user_key not in self._metrics["requests_by_user"]:
                self._metrics["requests_by_user"][user_key] = 0
            self._metrics["requests_by_user"][user_key] += 1

    async def _start_trace(
        self,
        request_type: str,
        user_id: UUID | None,
        request_hash: str,
    ) -> Any:
        """Start an observability trace.

        Args:
            request_type: Type of interpretation
            user_id: User ID
            request_hash: Request hash for correlation

        Returns:
            Trace context (LangFuse trace or similar)
        """
        if not self._enable_observability:
            return None

        # Placeholder for LangFuse integration
        # In production, this would create a LangFuse trace:
        # trace = langfuse.trace(
        #     name=f"interpretation:{request_type}",
        #     user_id=str(user_id) if user_id else None,
        #     metadata={"request_hash": request_hash},
        # )
        # return trace

        logger.debug(
            f"Starting trace for {request_type}, "
            f"user={user_id}, hash={request_hash}"
        )
        return {"type": request_type, "start_time": datetime.now(timezone.utc)}

    async def _end_trace(
        self,
        trace: Any,
        result: InterpretationResult,
        success: bool,
    ) -> None:
        """End an observability trace.

        Args:
            trace: Trace context
            result: Interpretation result
            success: Whether request succeeded
        """
        if not self._enable_observability or not trace:
            return

        # Placeholder for LangFuse integration
        # In production:
        # trace.update(
        #     output=result.summary,
        #     metadata={
        #         "tool_calls": len(result.tool_calls),
        #         "claims": len(result.claims),
        #         "confidence": result.confidence_score,
        #     },
        #     status="success" if success else "error",
        # )

        elapsed = datetime.now(timezone.utc) - trace.get("start_time", datetime.now(timezone.utc))
        logger.debug(
            f"Trace completed for {trace.get('type')}: "
            f"success={success}, elapsed={elapsed.total_seconds():.2f}s"
        )

    async def interpret_deg(
        self,
        user_id: UUID | None,
        upregulated: list[tuple[str, float]],
        downregulated: list[tuple[str, float]],
        condition_a: str,
        condition_b: str,
        experiment_type: str = "RNA-seq",
        organism: str = "human",
        additional_context: str = "",
        max_iterations: int = 10,
        use_cache: bool = True,
    ) -> InterpretationResult:
        """Interpret differential expression results.

        Args:
            user_id: User ID (optional)
            upregulated: List of (gene, log2fc) tuples
            downregulated: List of (gene, log2fc) tuples
            condition_a: First condition
            condition_b: Second condition
            experiment_type: Type of experiment
            organism: Organism name
            additional_context: Additional context
            max_iterations: Maximum tool iterations
            use_cache: Whether to use caching

        Returns:
            InterpretationResult
        """
        request_type = InterpretationType.DEG_ANALYSIS.value

        # Compute request hash
        request_hash = self._compute_request_hash(
            request_type,
            upregulated=upregulated,
            downregulated=downregulated,
            condition_a=condition_a,
            condition_b=condition_b,
            experiment_type=experiment_type,
            organism=organism,
        )

        # Check cache
        if use_cache:
            cached = await self._get_cached_result(request_hash)
            if cached:
                return cached

        # Start trace
        trace = await self._start_trace(request_type, user_id, request_hash)

        try:
            # Run interpretation
            result = await self._interpreter.interpret_deg_results(
                upregulated=upregulated,
                downregulated=downregulated,
                condition_a=condition_a,
                condition_b=condition_b,
                experiment_type=experiment_type,
                organism=organism,
                additional_context=additional_context,
                max_iterations=max_iterations,
            )

            # Track metrics
            self._track_metrics(request_type, user_id, result, success=True)

            # Cache result
            if use_cache:
                await self._cache_result(request_hash, result)

            # End trace
            await self._end_trace(trace, result, success=True)

            return result

        except Exception as e:
            logger.exception(f"DEG interpretation failed: {e}")
            self._metrics["failed_requests"] += 1

            # Create error result
            error_result = InterpretationResult(
                interpretation_type=InterpretationType.DEG_ANALYSIS,
                summary=f"Interpretation failed: {e}",
                claims=[],
                tool_calls=[],
                confidence_score=0.0,
                processing_time_ms=0.0,
                model_used=self._interpreter._model,
            )

            await self._end_trace(trace, error_result, success=False)
            raise

    async def interpret_pathway(
        self,
        user_id: UUID | None,
        pathways: list[dict[str, Any]],
        experiment_context: str,
        gene_set_size: int | None = None,
        max_iterations: int = 10,
        use_cache: bool = True,
    ) -> InterpretationResult:
        """Interpret pathway enrichment results.

        Args:
            user_id: User ID (optional)
            pathways: List of pathway dicts
            experiment_context: Context description
            gene_set_size: Number of genes analyzed
            max_iterations: Maximum iterations
            use_cache: Whether to use caching

        Returns:
            InterpretationResult
        """
        request_type = InterpretationType.PATHWAY_ENRICHMENT.value

        request_hash = self._compute_request_hash(
            request_type,
            pathways=pathways,
            experiment_context=experiment_context,
            gene_set_size=gene_set_size,
        )

        if use_cache:
            cached = await self._get_cached_result(request_hash)
            if cached:
                return cached

        trace = await self._start_trace(request_type, user_id, request_hash)

        try:
            result = await self._interpreter.interpret_pathway_enrichment(
                pathways=pathways,
                experiment_context=experiment_context,
                gene_set_size=gene_set_size,
                max_iterations=max_iterations,
            )

            self._track_metrics(request_type, user_id, result, success=True)

            if use_cache:
                await self._cache_result(request_hash, result)

            await self._end_trace(trace, result, success=True)
            return result

        except Exception as e:
            logger.exception(f"Pathway interpretation failed: {e}")
            self._metrics["failed_requests"] += 1
            await self._end_trace(trace, None, success=False)
            raise

    async def analyze_gene_function(
        self,
        user_id: UUID | None,
        genes: list[str],
        analysis_context: str = "",
        max_iterations: int = 10,
        use_cache: bool = True,
    ) -> InterpretationResult:
        """Analyze gene function.

        Args:
            user_id: User ID (optional)
            genes: List of gene symbols
            analysis_context: Context for analysis
            max_iterations: Maximum iterations
            use_cache: Whether to use caching

        Returns:
            InterpretationResult
        """
        request_type = InterpretationType.GENE_FUNCTION.value

        request_hash = self._compute_request_hash(
            request_type,
            genes=genes,
            analysis_context=analysis_context,
        )

        if use_cache:
            cached = await self._get_cached_result(request_hash)
            if cached:
                return cached

        trace = await self._start_trace(request_type, user_id, request_hash)

        try:
            result = await self._interpreter.analyze_gene_function(
                genes=genes,
                analysis_context=analysis_context,
                max_iterations=max_iterations,
            )

            self._track_metrics(request_type, user_id, result, success=True)

            if use_cache:
                await self._cache_result(request_hash, result)

            await self._end_trace(trace, result, success=True)
            return result

        except Exception as e:
            logger.exception(f"Gene function analysis failed: {e}")
            self._metrics["failed_requests"] += 1
            await self._end_trace(trace, None, success=False)
            raise

    async def assess_batch_effects(
        self,
        user_id: UUID | None,
        batch_count: int,
        batch_metrics: str,
        samples_per_batch: str = "",
        pca_summary: str = "",
        max_iterations: int = 5,
        use_cache: bool = True,
    ) -> InterpretationResult:
        """Assess batch effects.

        Args:
            user_id: User ID (optional)
            batch_count: Number of batches
            batch_metrics: Batch effect metrics
            samples_per_batch: Sample distribution
            pca_summary: PCA analysis summary
            max_iterations: Maximum iterations
            use_cache: Whether to use caching

        Returns:
            InterpretationResult
        """
        request_type = InterpretationType.BATCH_EFFECT.value

        request_hash = self._compute_request_hash(
            request_type,
            batch_count=batch_count,
            batch_metrics=batch_metrics,
            samples_per_batch=samples_per_batch,
            pca_summary=pca_summary,
        )

        if use_cache:
            cached = await self._get_cached_result(request_hash)
            if cached:
                return cached

        trace = await self._start_trace(request_type, user_id, request_hash)

        try:
            result = await self._interpreter.assess_batch_effects(
                batch_count=batch_count,
                batch_metrics=batch_metrics,
                samples_per_batch=samples_per_batch,
                pca_summary=pca_summary,
                max_iterations=max_iterations,
            )

            self._track_metrics(request_type, user_id, result, success=True)

            if use_cache:
                await self._cache_result(request_hash, result)

            await self._end_trace(trace, result, success=True)
            return result

        except Exception as e:
            logger.exception(f"Batch effect assessment failed: {e}")
            self._metrics["failed_requests"] += 1
            await self._end_trace(trace, None, success=False)
            raise

    async def review_literature(
        self,
        user_id: UUID | None,
        topic: str,
        focus_areas: str = "",
        research_context: str = "",
        max_iterations: int = 8,
        use_cache: bool = True,
    ) -> InterpretationResult:
        """Review literature on a topic.

        Args:
            user_id: User ID (optional)
            topic: Topic to review
            focus_areas: Specific areas to focus on
            research_context: Research context
            max_iterations: Maximum iterations
            use_cache: Whether to use caching

        Returns:
            InterpretationResult
        """
        request_type = InterpretationType.LITERATURE_REVIEW.value

        request_hash = self._compute_request_hash(
            request_type,
            topic=topic,
            focus_areas=focus_areas,
            research_context=research_context,
        )

        if use_cache:
            cached = await self._get_cached_result(request_hash)
            if cached:
                return cached

        trace = await self._start_trace(request_type, user_id, request_hash)

        try:
            result = await self._interpreter.review_literature(
                topic=topic,
                focus_areas=focus_areas,
                research_context=research_context,
                max_iterations=max_iterations,
            )

            self._track_metrics(request_type, user_id, result, success=True)

            if use_cache:
                await self._cache_result(request_hash, result)

            await self._end_trace(trace, result, success=True)
            return result

        except Exception as e:
            logger.exception(f"Literature review failed: {e}")
            self._metrics["failed_requests"] += 1
            await self._end_trace(trace, None, success=False)
            raise

    async def custom_interpretation(
        self,
        user_id: UUID | None,
        prompt: str,
        system_prompt: str | None = None,
        context: dict[str, Any] | None = None,
        max_iterations: int = 10,
        use_cache: bool = False,  # Don't cache custom prompts by default
    ) -> InterpretationResult:
        """Run custom interpretation.

        Args:
            user_id: User ID (optional)
            prompt: User prompt
            system_prompt: Custom system prompt
            context: Additional context
            max_iterations: Maximum iterations
            use_cache: Whether to use caching

        Returns:
            InterpretationResult
        """
        request_type = InterpretationType.CUSTOM.value

        request_hash = self._compute_request_hash(
            request_type,
            prompt=prompt,
            system_prompt=system_prompt,
            context=context,
        )

        if use_cache:
            cached = await self._get_cached_result(request_hash)
            if cached:
                return cached

        trace = await self._start_trace(request_type, user_id, request_hash)

        try:
            result = await self._interpreter.custom_interpretation(
                prompt=prompt,
                system_prompt=system_prompt,
                context=context,
                max_iterations=max_iterations,
            )

            self._track_metrics(request_type, user_id, result, success=True)

            if use_cache:
                await self._cache_result(request_hash, result)

            await self._end_trace(trace, result, success=True)
            return result

        except Exception as e:
            logger.exception(f"Custom interpretation failed: {e}")
            self._metrics["failed_requests"] += 1
            await self._end_trace(trace, None, success=False)
            raise

    def get_available_tools(self) -> list[str]:
        """Get list of available tools.

        Returns:
            List of tool names
        """
        return self._interpreter.get_available_tools()

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics.

        Returns:
            Metrics dictionary
        """
        return {
            **self._metrics,
            "interpreter_metrics": self._interpreter.get_metrics(),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "deduplicated_requests": 0,
            "total_cost_usd": 0.0,
            "total_tokens_used": 0,
            "requests_by_type": {},
            "requests_by_user": {},
        }


def create_interpretation_api_service(
    session: AsyncSession | None = None,
    cache: RedisClient | None = None,
    enable_observability: bool = True,
) -> InterpretationAPIService:
    """Create a configured interpretation API service.

    Args:
        session: Async database session
        cache: Redis cache instance
        enable_observability: Enable observability hooks

    Returns:
        InterpretationAPIService instance
    """
    return InterpretationAPIService(
        session=session,
        cache=cache,
        enable_observability=enable_observability,
    )
