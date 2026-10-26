"""FastAPI server for the Dogma web workspace."""

import asyncio
import hmac
import subprocess
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path as FilePath
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from quration.api.models import (
    AnalysisPlanModel,
    CancelExecutionResponse,
    ConditionModel,
    ErrorResponse,
    ExecutePipelineRequest,
    ExecutionListResponse,
    ExecutionResultModel,
    ExecutionStatusModel,
    ExperimentalDesignModel,
    FetchDataRequest,
    FetchDataResponse,
    GenerateAnalysisPlanRequest,
    GeoDatasetCandidateModel,
    GsmSampleModel,
    HealthResponse,
    PipelineInfoModel,
    ProgressEvent,
    ProteomicsAssayModel,
    ProteomicsConditionModel,
    ProteomicsDatasetCandidateModel,
    ProteomicsExperimentalDesignModel,
    ProteomicsQuerySpecModel,
    QuerySpecModel,
)
from quration.api.broker_routes import router as broker_router
from quration.api.hypothesis_routes import router as hypothesis_router

# Import context memory routers
try:
    from dotenv import load_dotenv
    from quration.api.dependencies import init_async_db, init_redis_cache
    from quration.api.routes import (
        context_router,
        health_router,
        interactions_legacy_router,
        interactions_router,
        preferences_router,
        searches_legacy_router,
        searches_router,
    )
    load_dotenv()  # Load .env for context memory
    CONTEXT_MEMORY_AVAILABLE = True
except ImportError as e:
    import traceback
    print(f"Context memory module import failed: {e}")
    traceback.print_exc()
    CONTEXT_MEMORY_AVAILABLE = False
    context_router = None  # type: ignore
    health_router = None  # type: ignore

from quration.data_sources.geo_search import search_geo
from quration.data_sources.geo_search_streaming_async import (
    search_geo_with_progress_async,
)
from quration.data_sources.proteomics_search import search_proteomics
from quration.models.geo_search import QuerySpec
from quration.models.nextflow import (
    ExecutePipelineResponse,
    GetExecutionStatusResponse,
    ListPipelinesRequest,
    OmicsType,
    PipelineStatus,
)
from quration.models.proteomics_search import ProteomicsQuerySpec
from quration.pipelines import (
    NextflowExecutor,
    OutputProcessor,
    get_pipeline_registry,
)

# Import observability components (lazy import to avoid circular dependencies)
try:
    from quration.observability import (
        ObservabilityMiddleware,
        PrometheusMiddleware,
        initialize_observability,
    )
    from quration.observability.config import ObservabilityConfig
    from quration.api.observability_routes import router as observability_router
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    observability_router = None  # type: ignore

logger = logging.getLogger(__name__)

# Conversation context storage (in-memory for now)
# In production, use Redis or similar
conversation_contexts: Dict[str, Dict] = {}

# Initialize unified Nextflow components
# Used by both /analysis/* and /pipelines/* endpoints
pipeline_registry = get_pipeline_registry()
nextflow_executor = NextflowExecutor()
output_processor = OutputProcessor()

# Clean up old contexts periodically (>1 hour old)
def cleanup_old_contexts():
    """Remove contexts older than 1 hour."""
    cutoff = datetime.now() - timedelta(hours=1)
    expired = [
        conv_id
        for conv_id, ctx in conversation_contexts.items()
        if ctx.get("timestamp", datetime.min) < cutoff
    ]
    for conv_id in expired:
        del conversation_contexts[conv_id]

# Create FastAPI app
app = FastAPI(
    title="Dogma API",
    description="Graph-grounded computational biology research API",
    version="0.1.0",
)

# Initialize observability and context memory on startup
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    # Initialize observability if available
    if OBSERVABILITY_AVAILABLE:
        try:
            # Initialize observability with default or environment-based config
            config = ObservabilityConfig()
            langfuse_client, metrics = initialize_observability(config)

            if langfuse_client and langfuse_client.enabled:
                logger.info("LangFuse observability initialized")
            if metrics and metrics._enabled:
                logger.info("Metrics collection initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize observability: {e}")
    else:
        logger.warning("Observability module not available")

    # Initialize context memory database and cache if available
    if CONTEXT_MEMORY_AVAILABLE:
        try:
            import os
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                init_async_db(database_url)
                logger.info("Context memory database initialized")
            else:
                logger.warning("DATABASE_URL not set. Context memory will be limited.")

            # Initialize Redis cache
            try:
                redis_cache = init_redis_cache()
                logger.info("Redis cache initialized")

                # Warm cache on startup if Redis is available
                if redis_cache and redis_cache.is_available():
                    try:
                        # Cache warming can be added here for frequently accessed data
                        # For now, just log that cache is ready
                        logger.info("Redis cache warming complete - ready for requests")
                    except Exception as e:
                        logger.warning(f"Cache warming failed: {e}. Cache still available for normal operations.")
            except Exception as e:
                logger.warning(f"Redis cache initialization failed: {e}. Continuing without cache.")
        except Exception as e:
            logger.warning(f"Failed to initialize context memory: {e}")
    else:
        logger.warning("Context memory module not available")

# Add observability middleware (before CORS)
if OBSERVABILITY_AVAILABLE:
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    # Include observability API routes
    if observability_router:
        app.include_router(observability_router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    + [
        origin.strip()
        for origin in os.getenv("DOGMA_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include broker routes
app.include_router(broker_router)
app.include_router(hypothesis_router)

# Register context memory routers if available
if CONTEXT_MEMORY_AVAILABLE:
    app.include_router(context_router)
    app.include_router(health_router)
    app.include_router(preferences_router)
    app.include_router(searches_router)
    app.include_router(interactions_router)
    # Register legacy /context/* routers for backward compatibility
    app.include_router(searches_legacy_router)
    app.include_router(interactions_legacy_router)
    logger.info("Context memory routers registered (including legacy /context/* endpoints)")


# Only register fallback health endpoint if context memory module is unavailable
if not CONTEXT_MEMORY_AVAILABLE:
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint (fallback when context memory is unavailable)."""
        return {"status": "ok"}


@app.post(
    "/geo/search",
    response_model=List[GeoDatasetCandidateModel],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def search_geo_datasets(
    query: QuerySpecModel,
    max_results: int = Query(
        default=50, ge=1, le=500, description="Maximum number of results to return"
    ),
    fetch_samples: bool = Query(
        default=False, description="Whether to fetch GSM sample records"
    ),
    max_samples_per_dataset: int = Query(
        default=50, ge=1, le=200, description="Max GSM samples to fetch per dataset"
    ),
):
    """
    Search GEO for datasets matching the query specification.

    This endpoint accepts a query specification and returns a list of matching
    GEO datasets with experimental design information and match reasons.

    Args:
        query: Query specification with disease terms, therapy info, genes, etc.
        max_results: Maximum number of datasets to return (1-500)
        fetch_samples: Whether to fetch individual GSM sample records
        max_samples_per_dataset: Maximum GSM samples per dataset (1-200)

    Returns:
        List of GeoDatasetCandidate objects matching the query

    Raises:
        HTTPException: 400 for invalid input, 500 for server errors
    """
    try:
        # Validate input
        if not query.disease_terms:
            raise HTTPException(
                status_code=400,
                detail="At least one disease term is required",
            )

        # Convert Pydantic model to dataclass
        spec = QuerySpec(
            disease_terms=query.disease_terms,
            therapy_class=query.therapy_class,
            therapy_scope=query.therapy_scope,
            targets_or_genes=query.targets_or_genes,
            study_keywords=query.study_keywords,
            must_have_clinical=query.must_have_clinical,
            min_samples=query.min_samples,
        )

        # Execute search
        candidates = search_geo(
            spec=spec,
            max_results=max_results,
            fetch_samples=fetch_samples,
            max_samples_per_dataset=max_samples_per_dataset,
        )

        # Convert dataclasses to Pydantic models
        result = []
        for candidate in candidates:
            # Convert experimental design
            exp_design = ExperimentalDesignModel(
                conditions=[
                    ConditionModel(name=c.name, n=c.n)
                    for c in (candidate.experimental_design.conditions or [])
                ],
                design_type=candidate.experimental_design.design_type,
                tech=candidate.experimental_design.tech,
                notes=candidate.experimental_design.notes,
                is_partial=candidate.experimental_design.is_partial,
            )

            # Convert samples
            samples = [
                GsmSampleModel(
                    gsm_id=s.gsm_id,
                    title=s.title,
                    sample_type=s.sample_type,
                    characteristics=s.characteristics,
                    raw_metadata=s.raw_metadata,
                )
                for s in candidate.samples
            ]

            # Create candidate model
            candidate_model = GeoDatasetCandidateModel(
                gse_id=candidate.gse_id,
                title=candidate.title,
                summary=candidate.summary,
                organism=candidate.organism,
                experimental_design=exp_design,
                n_samples=candidate.n_samples,
                platforms=candidate.platforms,
                primary_pmid=candidate.primary_pmid,
                maybe_has_survival_data=candidate.maybe_has_survival_data,
                match_reasons=candidate.match_reasons,
                raw_metadata=candidate.raw_metadata,
                matched_queries=candidate.matched_queries,
                samples=samples,
                samples_fetched=candidate.samples_fetched,
            )
            result.append(candidate_model)

        return result

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Error in search_geo_datasets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@app.post("/geo/search/stream")
async def search_geo_datasets_stream(
    query: QuerySpecModel,
    conversation_id: Optional[str] = Query(None, description="Conversation ID for context"),
    max_results: int = Query(default=50, ge=1, le=500),
    fetch_samples: bool = Query(default=False),
    max_samples_per_dataset: int = Query(default=50, ge=1, le=200),
):
    """
    Stream GEO search results with real-time progress updates via Server-Sent Events.

    This endpoint performs the same search as /geo/search but streams progress
    events as the search progresses, enabling real-time UI updates.

    Args:
        query: Query specification
        conversation_id: Optional conversation ID for storing results in context
        max_results: Maximum number of results
        fetch_samples: Whether to fetch GSM samples
        max_samples_per_dataset: Max samples per dataset

    Returns:
        Server-Sent Events stream with progress updates and final results
    """

    async def event_generator():
        """Generate SSE events during search."""
        try:
            # Validate input
            if not query.disease_terms:
                error_event = ProgressEvent(
                    step="error",
                    status="error",
                    message="At least one disease term is required"
                )
                yield f"data: {error_event.model_dump_json()}\n\n"
                return

            # Convert to QuerySpec
            spec = QuerySpec(
                disease_terms=query.disease_terms,
                therapy_class=query.therapy_class,
                therapy_scope=query.therapy_scope,
                targets_or_genes=query.targets_or_genes,
                study_keywords=query.study_keywords,
                must_have_clinical=query.must_have_clinical,
                min_samples=query.min_samples,
            )

            # Create async queue for real-time event streaming
            event_queue: asyncio.Queue = asyncio.Queue()
            search_complete = asyncio.Event()
            search_results = []
            search_error = None

            # Progress callback that puts events in queue for immediate yielding
            async def emit_progress(**kwargs):
                event = ProgressEvent(**kwargs)
                await event_queue.put(event)

            # Run search in background task
            async def run_search():
                nonlocal search_results, search_error
                try:
                    results = await search_geo_with_progress_async(
                        spec=spec,
                        progress_callback=emit_progress,
                        max_results=max_results,
                        fetch_samples=fetch_samples,
                        max_samples_per_dataset=max_samples_per_dataset,
                    )
                    search_results = results
                except Exception as e:
                    search_error = e
                finally:
                    search_complete.set()

            # Start search task
            search_task = asyncio.create_task(run_search())

            # Yield events as they arrive in queue
            while not search_complete.is_set() or not event_queue.empty():
                try:
                    # Wait for event with timeout to check if search is done
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield f"data: {event.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # No event yet, continue waiting
                    continue

            # Check for search errors
            if search_error:
                raise search_error

            # Search completed successfully
            candidates = search_results

            # Convert results to Pydantic models
            result = []
            for candidate in candidates:
                exp_design = ExperimentalDesignModel(
                    conditions=[
                        ConditionModel(name=c.name, n=c.n)
                        for c in (candidate.experimental_design.conditions or [])
                    ],
                    design_type=candidate.experimental_design.design_type,
                    tech=candidate.experimental_design.tech,
                    notes=candidate.experimental_design.notes,
                    is_partial=candidate.experimental_design.is_partial,
                )

                samples = [
                    GsmSampleModel(
                        gsm_id=s.gsm_id,
                        title=s.title,
                        sample_type=s.sample_type,
                        characteristics=s.characteristics,
                        raw_metadata=s.raw_metadata,
                    )
                    for s in candidate.samples
                ]

                candidate_model = GeoDatasetCandidateModel(
                    gse_id=candidate.gse_id,
                    title=candidate.title,
                    summary=candidate.summary,
                    organism=candidate.organism,
                    experimental_design=exp_design,
                    n_samples=candidate.n_samples,
                    platforms=candidate.platforms,
                    primary_pmid=candidate.primary_pmid,
                    maybe_has_survival_data=candidate.maybe_has_survival_data,
                    match_reasons=candidate.match_reasons,
                    raw_metadata=candidate.raw_metadata,
                    matched_queries=candidate.matched_queries,
                    samples=samples,
                    samples_fetched=candidate.samples_fetched,
                )
                result.append(candidate_model)

            # Store in conversation context if ID provided
            if conversation_id:
                cleanup_old_contexts()
                conversation_contexts[conversation_id] = {
                    "timestamp": datetime.now(),
                    "results": [r.model_dump(by_alias=True) for r in result],
                    "query": query.model_dump(by_alias=True),
                }

            # Send final results event
            final_event = ProgressEvent(
                step="complete",
                status="complete",
                message=f"Search complete! Found {len(result)} datasets",
                data={"results": [r.model_dump(by_alias=True) for r in result]},
            )
            yield f"data: {final_event.model_dump_json()}\n\n"

        except Exception as e:
            error_event = ProgressEvent(
                step="error",
                status="error",
                message=f"Search failed: {str(e)}",
                data={"error": str(e)},
            )
            yield f"data: {error_event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.get("/geo/context/{conversation_id}")
async def get_conversation_context(
    conversation_id: str = Path(..., description="Conversation ID"),
):
    """
    Retrieve cached search results for a conversation.

    This enables context-aware follow-up questions without re-running searches.

    Args:
        conversation_id: The conversation identifier

    Returns:
        Cached search results and query if available

    Raises:
        HTTPException: 404 if no context found
    """
    cleanup_old_contexts()

    if conversation_id not in conversation_contexts:
        raise HTTPException(
            status_code=404,
            detail=f"No context found for conversation {conversation_id}",
        )

    return conversation_contexts[conversation_id]


# ============================================================================
# Single-Cell RNA-seq Endpoints
# ============================================================================


@app.get("/single-cell/search")
async def search_single_cell_datasets(
    query: str = Query(..., description="Search query (e.g., 'breast cancer')"),
    organism: str = Query("Homo sapiens", description="Organism filter"),
    tissue: str | None = Query(None, description="Tissue filter (optional)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
):
    """
    Search GEO for single-cell RNA-seq datasets.

    Returns datasets with information about supplementary files.
    """
    try:
        from quration.data_sources.single_cell.adapters.geo_scrna import (
            GEOSingleCellFetcher,
        )

        fetcher = GEOSingleCellFetcher()

        # Search by therapeutic area
        results = fetcher.search_single_cell_by_therapeutic_area(
            disease=query, tissue=tissue, organism=organism, limit=limit
        )

        return {
            "query": query,
            "organism": organism,
            "tissue": tissue,
            "n_results": len(results),
            "datasets": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/single-cell/dataset/{accession}")
async def get_single_cell_dataset_info(
    accession: str = Path(..., description="GSE accession (e.g., GSE123456)")
):
    """
    Get detailed information about a single-cell dataset.

    Includes available supplementary files.
    """
    try:
        from quration.data_sources.single_cell.adapters.geo_scrna import (
            GEOSingleCellFetcher,
        )

        fetcher = GEOSingleCellFetcher()

        # Get summary
        summary = fetcher.fetch_dataset_summary(accession)

        # Get supplementary files
        supp_files = fetcher.get_supplementary_file_urls(accession)

        return {
            "accession": accession,
            "title": summary.get("title", ""),
            "summary": summary.get("summary", ""),
            "organism": summary.get("taxon", ""),
            "supplementary_files": supp_files,
            "has_h5ad": len(supp_files["h5ad"]) > 0,
            "has_mtx": len(supp_files["mtx"]) > 0,
        }

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {str(e)}")


# ============================================================================
# ANALYSIS HELPER ENDPOINTS
# ============================================================================
# These provide unique analysis features (plan generation, data fetching)
# For pipeline execution, use /pipelines/* endpoints instead


@app.post("/analysis/plan", response_model=AnalysisPlanModel)
async def generate_analysis_plan(request: GenerateAnalysisPlanRequest):
    """
    Generate an analysis plan from curated dataset metadata.

    Uses LLM to analyze the curated metadata and recommend:
    - Appropriate nf-core pipelines
    - Reference genome
    - Experimental comparisons
    - Expected outputs

    Args:
        request: Contains curated dataset metadata

    Returns:
        Analysis plan with pipeline recommendations
    """
    try:
        from quration.analysis.plan_generator import PlanGenerator

        plan_gen = PlanGenerator()
        plan = await plan_gen.generate_plan_async(request.curatedDataset)

        return AnalysisPlanModel(
            recommendedPipeline=plan.recommended_pipeline,
            referenceGenome=plan.reference_genome,
            libraryStrategy=plan.library_strategy,
            comparisons=plan.comparisons,
            expectedOutputs=plan.expected_outputs,
            reasoning=plan.reasoning,
            configSuggestions=plan.config_suggestions,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analysis plan: {str(e)}"
        )


@app.post("/analysis/fetch", response_model=FetchDataResponse)
async def fetch_raw_data(request: FetchDataRequest):
    """
    Fetch raw data files for a GEO dataset.

    Downloads SRA files and converts to FASTQ format.

    Args:
        request: Contains GEO accession and sample information

    Returns:
        Paths to downloaded FASTQ files
    """
    try:
        from quration.analysis.data_fetcher import DataFetcher

        fetcher = DataFetcher()
        result = await fetcher.fetch_dataset_async(
            request.geoAccession,
            request.samples
        )

        return FetchDataResponse(
            geoAccession=result.geo_accession,
            fastqFiles=result.fastq_files,
            downloadPath=str(result.download_path),
            totalSize=result.total_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch raw data: {str(e)}"
        )


# ============================================================================
# PIPELINE EXECUTION ENDPOINTS
# ============================================================================
# Use /pipelines/* endpoints for executing and monitoring pipelines


@app.get("/pipelines", tags=["Nextflow"])
async def list_pipelines(
    omics_type: Optional[OmicsType] = Query(None, description="Filter by omics type"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    enabled_only: bool = Query(True, description="Only show enabled pipelines"),
):
    """
    List available Nextflow pipelines.

    Returns a catalog of available nf-core and custom pipelines with their
    parameters, documentation, and metadata.

    Args:
        omics_type: Filter pipelines by omics type (bulk_rnaseq, single_cell, etc.)
        search: Search string to filter pipelines by name or description
        tags: Comma-separated list of tags to filter by
        enabled_only: Only return enabled pipelines

    Returns:
        List of pipeline catalog entries
    """
    try:
        tag_list = tags.split(",") if tags else None
        pipelines = pipeline_registry.list_pipelines(
            omics_type=omics_type,
            search=search,
            tags=tag_list,
            enabled_only=enabled_only,
        )
        return [p.model_dump() for p in pipelines]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list pipelines: {str(e)}",
        )


@app.get("/pipelines/{pipeline_id}", tags=["Nextflow"])
async def get_pipeline_details(
    pipeline_id: str = Path(..., description="Pipeline ID (e.g., 'nf-core/rnaseq')"),
):
    """
    Get detailed information about a specific pipeline.

    Args:
        pipeline_id: The pipeline identifier (e.g., 'nf-core/rnaseq')

    Returns:
        Detailed pipeline information including parameters

    Raises:
        HTTPException: 404 if pipeline not found
    """
    # URL decode the pipeline_id to handle 'nf-core/rnaseq' format
    pipeline_id = pipeline_id.replace("%2F", "/")

    pipeline = pipeline_registry.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline not found: {pipeline_id}",
        )

    return pipeline.model_dump()


_claim_execution_service = None


def claim_execution_service():
    """Enable only for a server-configured local workspace with pinned specs."""
    global _claim_execution_service
    if _claim_execution_service is None:
        root = os.environ.get('DOGMA_EXECUTION_WORKSPACE')
        if not root:
            raise HTTPException(status_code=409, detail='No local execution workspace configured')
        from quration.api.hypothesis_routes import get_repo
        from quration.pipelines.claim_execution_service import ClaimExecutionService
        from quration.pipelines.execution_contract import contained, digest

        def specification(graph_id, edge_id):
            path = contained(root, '.dogma/execution-specs/' + digest([graph_id, edge_id])[7:] + '.json')
            result = json.loads(path.read_text())
            result["_specification_file"] = str(path.relative_to(FilePath(root).resolve()))
            return result

        def preflight():
            launcher = FilePath(__file__).resolve().parents[3] / 'bin/dogma'
            try:
                completed = subprocess.run([str(launcher), 'methods-graph-preflight', root, '--format', 'json'],
                    text=True, capture_output=True, timeout=45)
                result = json.loads(completed.stdout)
                if completed.returncode != 0 or not isinstance(result, dict):
                    raise ValueError('preflight CLI did not return a valid report')
                return result
            except (OSError, ValueError, subprocess.TimeoutExpired):
                raise ValueError('Bundled Dogma preflight is unavailable or failed; configure the methods graph and verification CLI')

        _claim_execution_service = ClaimExecutionService(root, get_repo(), nextflow_executor,
            specification, preflight)
    return _claim_execution_service


def require_local_execution_request(request):
    # Browser cross-origin calls and remote clients cannot grant local execution.
    if not request.client or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(status_code=403, detail='Local execution requires a loopback client')
    if request.headers.get('origin') or request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(status_code=403, detail='Cross-origin local execution is disabled')
    token = os.environ.get('DOGMA_LOCAL_EXECUTION_TOKEN')
    supplied = request.headers.get('authorization', '')
    if not token or len(token) < 32 or not hmac.compare_digest(supplied, 'Bearer ' + token):
        raise HTTPException(status_code=403, detail='Authenticated local execution required')
    if request.headers.get('x-dogma-local-execution') != 'explicitly-authorized':
        raise HTTPException(status_code=403, detail='Explicit local execution authorization required')


@app.post('/pipelines/claims/{graph_id}/{edge_id}/plan')
async def plan_claim_execution(graph_id: str, edge_id: str, request: Request):
    require_local_execution_request(request)
    try:
        return claim_execution_service().plan(graph_id, edge_id)
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=409, detail=str(error))


@app.post('/pipelines/plans/{plan_id}/approve')
async def approve_claim_execution(plan_id: str, body: dict, request: Request):
    require_local_execution_request(request)
    try:
        return claim_execution_service().approve(plan_id, body.get('context_digest'),
            local_execution_authorized=body.get('local_execution_authorized') is True)
    except (ValueError, KeyError, OSError) as error:
        raise HTTPException(status_code=409, detail=str(error))


@app.post('/pipelines/plans/{plan_id}/execute')
async def execute_claim_plan(plan_id: str, request: Request):
    require_local_execution_request(request)
    try:
        return await claim_execution_service().execute(plan_id)
    except (ValueError, KeyError, OSError) as error:
        raise HTTPException(status_code=409, detail=str(error))


@app.post("/pipelines/execute", response_model=ExecutePipelineResponse, tags=["Nextflow"])
async def execute_pipeline(request: ExecutePipelineRequest):
    """Legacy direct execution is closed; use an approved claim execution plan."""
    raise HTTPException(status_code=409, detail="Direct pipeline execution is disabled: a server-derived claim context, explicit bound approval, workspace trust, and verified preflight are required.")


@app.get("/pipelines/executions/{execution_id}", response_model=GetExecutionStatusResponse, tags=["Nextflow"])
async def get_execution_status(
    execution_id: str = Path(..., description="Execution ID"),
    include_logs: bool = Query(False, description="Include recent log output"),
    log_lines: int = Query(100, description="Number of log lines to include", ge=1, le=10000),
):
    """
    Get the status of a pipeline execution.

    Args:
        execution_id: The execution identifier
        include_logs: Whether to include recent log output
        log_lines: Number of log lines to include (if include_logs is True)

    Returns:
        Execution status and details

    Raises:
        HTTPException: 404 if execution not found
    """
    execution = nextflow_executor.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=404,
            detail=f"Execution not found: {execution_id}",
        )

    logs = None
    if include_logs:
        logs = nextflow_executor.get_execution_logs(execution_id, tail_lines=log_lines)

    return GetExecutionStatusResponse(
        execution=execution,
        logs=logs,
    )


@app.get("/pipelines/executions", tags=["Nextflow"])
async def list_executions(
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline ID"),
    status: Optional[PipelineStatus] = Query(None, description="Filter by status"),
):
    """
    List pipeline executions.

    Args:
        pipeline_id: Filter by pipeline ID
        status: Filter by execution status

    Returns:
        List of pipeline executions
    """
    executions = nextflow_executor.list_executions(
        pipeline_id=pipeline_id,
        status=status,
    )

    return [e.model_dump() for e in executions]


@app.delete("/pipelines/executions/{execution_id}", tags=["Nextflow"])
async def cancel_execution(
    execution_id: str = Path(..., description="Execution ID to cancel"),
):
    """
    Cancel a running pipeline execution.

    Args:
        execution_id: The execution identifier

    Returns:
        Success message

    Raises:
        HTTPException: 404 if execution not found, 400 if cannot be cancelled
    """
    success = await nextflow_executor.cancel_execution(execution_id)

    if not success:
        execution = nextflow_executor.get_execution(execution_id)
        if not execution:
            raise HTTPException(
                status_code=404,
                detail=f"Execution not found: {execution_id}",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel execution in status: {execution.status}",
            )

    return {"message": f"Execution {execution_id} cancelled successfully"}


@app.get("/pipelines/executions/{execution_id}/output", tags=["Nextflow"])
async def get_execution_output(
    execution_id: str = Path(..., description="Execution ID"),
):
    """
    Get processed output from a completed pipeline execution.

    This endpoint processes the pipeline outputs and maps them to the
    quration metadata schema.

    Args:
        execution_id: The execution identifier

    Returns:
        Processed pipeline output with metadata mapping

    Raises:
        HTTPException: 404 if execution not found, 400 if not completed
    """
    execution = nextflow_executor.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=404,
            detail=f"Execution not found: {execution_id}",
        )

    if execution.status != PipelineStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline execution is not completed. Current status: {execution.status}",
        )

    try:
        pipeline_output = output_processor.process_execution_output(execution)
        return pipeline_output.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process pipeline output: {str(e)}",
        )


# ============================================================================
# Proteomics Endpoints
# ============================================================================


@app.post(
    "/proteomics/search",
    response_model=List[ProteomicsDatasetCandidateModel],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def search_proteomics_datasets(
    query: ProteomicsQuerySpecModel,
    max_results: int = Query(
        default=50, ge=1, le=500, description="Maximum number of results to return"
    ),
    use_llm: bool = Query(
        default=True, description="Use LLM for intelligent query generation"
    ),
):
    """
    Search proteomics datasets (PRIDE Archive) matching the query specification.

    This endpoint accepts a query specification and returns a list of matching
    proteomics datasets with experimental design information and match reasons.

    Args:
        query: Query specification with disease terms, therapy info, proteins, etc.
        max_results: Maximum number of datasets to return (1-500)
        use_llm: Whether to use LLM for intelligent query generation

    Returns:
        List of ProteomicsDatasetCandidate objects matching the query

    Raises:
        HTTPException: 400 for invalid input, 500 for server errors
    """
    try:
        # Validate input
        if not query.disease_terms:
            raise HTTPException(
                status_code=400,
                detail="At least one disease term is required",
            )

        # Convert Pydantic model to dataclass
        spec = ProteomicsQuerySpec(
            disease_terms=query.disease_terms,
            therapy_class=query.therapy_class,
            therapy_scope=query.therapy_scope,
            targets_or_proteins=query.targets_or_proteins,
            study_keywords=query.study_keywords,
            must_have_quantification=query.must_have_quantification,
            min_samples=query.min_samples,
            organism=query.organism,
        )

        # Execute search
        search_result = search_proteomics(
            spec=spec,
            max_results=max_results,
            use_llm=use_llm,
        )

        # Convert dataclasses to Pydantic models
        result = []
        for candidate in search_result.candidates:
            # Convert experimental design
            exp_design = ProteomicsExperimentalDesignModel(
                conditions=[
                    ProteomicsConditionModel(
                        name=c.name,
                        n_replicates=c.n_replicates,
                        treatment=c.treatment,
                    )
                    for c in (candidate.experimental_design.conditions or [])
                ],
                design_type=candidate.experimental_design.design_type,
                instrument=candidate.experimental_design.instrument,
                quantification_method=candidate.experimental_design.quantification_method,
                acquisition_strategy=candidate.experimental_design.acquisition_strategy,
                notes=candidate.experimental_design.notes,
                is_partial=candidate.experimental_design.is_partial,
            )

            # Convert assays if fetched
            assay_models = []
            if candidate.assays_fetched:
                for assay in candidate.assays:
                    assay_models.append(
                        ProteomicsAssayModel(
                            assay_id=assay.assay_id,
                            title=assay.title,
                            sample_type=assay.sample_type,
                            characteristics=assay.characteristics,
                            raw_metadata=assay.raw_metadata,
                        )
                    )

            # Create candidate model
            candidate_model = ProteomicsDatasetCandidateModel(
                accession=candidate.accession,
                title=candidate.title,
                description=candidate.description,
                experimental_design=exp_design,
                n_assays=candidate.n_assays,
                organism=candidate.organism,
                instruments=candidate.instruments,
                experiment_types=candidate.experiment_types,
                quantification_methods=candidate.quantification_methods,
                tissues=candidate.tissues,
                diseases=candidate.diseases,
                cell_types=candidate.cell_types,
                primary_doi=candidate.primary_doi,
                primary_pmid=candidate.primary_pmid,
                has_protein_data=candidate.has_protein_data,
                has_peptide_data=candidate.has_peptide_data,
                has_quantification_data=candidate.has_quantification_data,
                match_reasons=candidate.match_reasons,
                matched_queries=candidate.matched_queries,
                raw_metadata=candidate.raw_metadata,
                assays=assay_models,
                assays_fetched=candidate.assays_fetched,
            )

            result.append(candidate_model)

        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "quration.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
