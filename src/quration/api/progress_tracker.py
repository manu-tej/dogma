"""Progress tracking for streaming GEO search operations."""

import time
from typing import Any, Callable, Optional
from .models import ProgressEvent


class SearchProgressTracker:
    """Tracks and emits progress events during GEO search operations.

    This class manages the lifecycle of a search operation, emitting events
    at each major step to enable real-time progress updates via SSE.
    """

    def __init__(self, emit_callback: Callable[[ProgressEvent], None]):
        """Initialize tracker with callback for emitting events.

        Args:
            emit_callback: Function to call when emitting progress events
        """
        self.emit = emit_callback
        self.start_time = time.time()
        self.detail_mode = False  # Switches to True after 10 seconds

    def elapsed_time(self) -> float:
        """Get elapsed time since search started."""
        return time.time() - self.start_time

    def should_show_detail(self) -> bool:
        """Determine if detailed progress should be shown.

        Adaptive detail: Show detailed progress (e.g., "dataset 5/10")
        only for slow queries that take >10 seconds.
        """
        if self.elapsed_time() > 10.0 and not self.detail_mode:
            self.detail_mode = True
        return self.detail_mode

    def step_start(
        self,
        step: str,
        message: str,
        total: Optional[int] = None,
        data: Optional[Any] = None
    ) -> None:
        """Emit event for step starting.

        Args:
            step: Step identifier (e.g., "query_generation")
            message: Human-readable message
            total: Total items to process in this step (optional)
            data: Additional step-specific data (optional)
        """
        event = ProgressEvent(
            step=step,
            status="running",
            message=message,
            progress=None if total is None else 0,
            total=total,
            data=data
        )
        self.emit(event)

    def step_progress(
        self,
        step: str,
        message: str,
        progress: int,
        total: int,
        data: Optional[Any] = None
    ) -> None:
        """Emit event for step progress update.

        Only emitted in detail mode (queries >10 seconds).

        Args:
            step: Step identifier
            message: Human-readable message with progress
            progress: Current progress count
            total: Total items to process
            data: Additional step-specific data (optional)
        """
        if self.should_show_detail():
            event = ProgressEvent(
                step=step,
                status="running",
                message=message,
                progress=progress,
                total=total,
                data=data
            )
            self.emit(event)

    def step_complete(
        self,
        step: str,
        message: str,
        data: Optional[Any] = None
    ) -> None:
        """Emit event for step completion.

        Args:
            step: Step identifier
            message: Human-readable completion message
            data: Additional step-specific data (optional)
        """
        event = ProgressEvent(
            step=step,
            status="complete",
            message=message,
            data=data
        )
        self.emit(event)

    def step_error(
        self,
        step: str,
        message: str,
        error: Optional[Exception] = None
    ) -> None:
        """Emit event for step error.

        Args:
            step: Step identifier
            message: Human-readable error message
            error: The exception that occurred (optional)
        """
        event = ProgressEvent(
            step=step,
            status="error",
            message=message,
            data={"error": str(error)} if error else None
        )
        self.emit(event)

    def search_complete(
        self,
        total_results: int,
        elapsed_seconds: float
    ) -> None:
        """Emit final completion event.

        Args:
            total_results: Number of datasets found
            elapsed_seconds: Total search time
        """
        event = ProgressEvent(
            step="complete",
            status="complete",
            message=f"Found {total_results} datasets in {elapsed_seconds:.1f}s",
            data={
                "total_results": total_results,
                "elapsed_seconds": elapsed_seconds
            }
        )
        self.emit(event)


# Progress step identifiers (for consistency)
STEP_QUERY_GENERATION = "query_generation"
STEP_NCBI_SEARCH = "ncbi_search"
STEP_METADATA_FETCH = "metadata_fetch"
STEP_DESIGN_PARSING = "design_parsing"
STEP_FILTERING = "filtering"
STEP_RESULTS = "results"
