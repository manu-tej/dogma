"""
API routes for Method Broker functionality.
"""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from quration.api.models import ErrorResponse
from quration.broker import (
    AnalysisMethod,
    MethodBroker,
    MethodProposal,
    MethodRequest,
    MethodResponse,
    ProposalManager,
)
from quration.config import get_config

# Create router
router = APIRouter(prefix="/broker", tags=["Method Broker"])

# Initialize broker and proposal manager lazily
# In production, these should be dependency-injected
_broker = None
_proposal_manager = None


def get_broker():
    """Get or create broker instance."""
    global _broker
    if _broker is None:
        config = get_config()
        _broker = MethodBroker(config)
    return _broker


def get_proposal_manager():
    """Get or create proposal manager instance."""
    global _proposal_manager
    if _proposal_manager is None:
        _proposal_manager = ProposalManager()
    return _proposal_manager


@router.post(
    "/match",
    response_model=MethodResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def match_methods(request: MethodRequest):
    """
    Match user request to appropriate analysis methods.

    This endpoint:
    1. Parses the natural language query using LLM
    2. Extracts structured requirements (data modality, analysis type, etc.)
    3. Matches against method registry using heuristic scoring
    4. Returns ranked method recommendations

    Args:
        request: Method request with natural language query and preferences

    Returns:
        MethodResponse with parsed request and ranked method matches

    Example:
        ```
        POST /broker/match
        {
            "query": "I need to call variants from whole genome sequencing data",
            "max_recommendations": 5,
            "prefer_published": true
        }
        ```
    """
    try:
        # Process the request
        broker = get_broker()
        response = await broker.process_request(request)
        return response

    except ValueError as e:
        if "ANTHROPIC_API_KEY" in str(e):
            raise HTTPException(
                status_code=500,
                detail="LLM API key not configured. Please set ANTHROPIC_API_KEY environment variable.",
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error in match_methods: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to match methods: {str(e)}",
        )


@router.get(
    "/methods",
    response_model=List[AnalysisMethod],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_methods(
    category: Optional[str] = Query(
        None, description="Filter by category (e.g., 'variant_calling', 'rna_seq')"
    ),
    modality: Optional[str] = Query(
        None,
        description="Filter by data modality (e.g., 'dna_seq', 'rna_seq')",
    ),
    search: Optional[str] = Query(None, description="Search by keyword"),
):
    """
    List all available analysis methods.

    Supports filtering by category, modality, and keyword search.

    Args:
        category: Filter by method category
        modality: Filter by supported data modality
        search: Keyword search

    Returns:
        List of analysis methods

    Example:
        ```
        GET /broker/methods?category=variant_calling&modality=dna_seq
        ```
    """
    try:
        broker = get_broker()

        if search:
            # Keyword search
            methods = broker.search_methods(search)
        else:
            # List with optional filters
            from quration.broker.models import DataModality, MethodCategory

            cat = MethodCategory(category) if category else None
            mod = DataModality(modality) if modality else None

            methods = broker.registry.list_methods(category=cat, modality=mod)

        return methods

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filter value: {str(e)}",
        )
    except Exception as e:
        print(f"Error in list_methods: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list methods: {str(e)}",
        )


@router.get(
    "/methods/{method_id}",
    response_model=AnalysisMethod,
    responses={
        404: {"model": ErrorResponse, "description": "Method not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_method(method_id: str):
    """
    Get detailed information about a specific method.

    Args:
        method_id: Method identifier

    Returns:
        AnalysisMethod details

    Example:
        ```
        GET /broker/methods/gatk-germline-variant-calling
        ```
    """
    try:
        broker = get_broker()
        method = broker.get_method(method_id)

        if not method:
            raise HTTPException(
                status_code=404,
                detail=f"Method '{method_id}' not found",
            )

        return method

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_method: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve method: {str(e)}",
        )


@router.get("/stats")
async def get_stats():
    """
    Get statistics about the method registry and proposals.

    Returns:
        Dictionary with registry and proposal statistics

    Example:
        ```
        GET /broker/stats
        ```

        Response:
        ```json
        {
            "registry": {
                "total_methods": 5,
                "by_category": {...},
                "average_quality_score": 0.95
            },
            "proposals": {
                "total_proposals": 10,
                "by_status": {...}
            }
        }
        ```
    """
    try:
        broker = get_broker()
        proposal_manager = get_proposal_manager()

        return {
            "registry": broker.get_registry_stats(),
            "proposals": proposal_manager.get_proposal_stats(),
        }

    except Exception as e:
        print(f"Error in get_stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve stats: {str(e)}",
        )


@router.post(
    "/proposals",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def submit_proposal(proposal: MethodProposal):
    """
    Submit a proposal for a new method to be added to the registry.

    Users can request new methods that they need but aren't currently available.
    Proposals are reviewed before being added to the registry.

    Args:
        proposal: Method proposal details

    Returns:
        Dictionary with proposal ID

    Example:
        ```
        POST /broker/proposals
        {
            "name": "AlphaFold Protein Structure Prediction",
            "category": "protein_structure",
            "description": "AI-powered protein structure prediction",
            "justification": "Need this for structural analysis of proteins",
            "use_cases": ["Predict protein structures from sequences"],
            "repository_url": "https://github.com/deepmind/alphafold",
            "proposed_by": "user123"
        }
        ```
    """
    try:
        proposal_manager = get_proposal_manager()
        proposal_id = proposal_manager.submit_proposal(proposal)

        return {
            "proposal_id": proposal_id,
            "status": "submitted",
            "message": "Proposal submitted successfully. It will be reviewed by administrators.",
        }

    except Exception as e:
        print(f"Error in submit_proposal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit proposal: {str(e)}",
        )


@router.get(
    "/proposals",
    response_model=List[MethodProposal],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_proposals(
    status: Optional[str] = Query(
        None, description="Filter by status (pending, approved, rejected)"
    ),
    proposed_by: Optional[str] = Query(None, description="Filter by user"),
):
    """
    List method proposals.

    Args:
        status: Filter by proposal status
        proposed_by: Filter by proposer user ID

    Returns:
        List of method proposals

    Example:
        ```
        GET /broker/proposals?status=pending
        ```
    """
    try:
        proposal_manager = get_proposal_manager()
        proposals = proposal_manager.list_proposals(
            status=status, proposed_by=proposed_by
        )
        return proposals

    except Exception as e:
        print(f"Error in list_proposals: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list proposals: {str(e)}",
        )


@router.get(
    "/proposals/{proposal_id}",
    response_model=MethodProposal,
    responses={
        404: {"model": ErrorResponse, "description": "Proposal not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_proposal(proposal_id: str):
    """
    Get details of a specific proposal.

    Args:
        proposal_id: Proposal identifier

    Returns:
        MethodProposal details
    """
    try:
        proposal_manager = get_proposal_manager()
        proposal = proposal_manager.get_proposal(proposal_id)

        if not proposal:
            raise HTTPException(
                status_code=404,
                detail=f"Proposal '{proposal_id}' not found",
            )

        return proposal

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_proposal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve proposal: {str(e)}",
        )


@router.patch(
    "/proposals/{proposal_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Proposal not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def update_proposal_status(
    proposal_id: str,
    status: str = Query(..., description="New status (pending, approved, rejected)"),
    review_notes: Optional[str] = Query(None, description="Review notes"),
):
    """
    Update the status of a proposal (admin only).

    Args:
        proposal_id: Proposal identifier
        status: New status
        review_notes: Optional review notes

    Returns:
        Success message
    """
    try:
        # Validate status
        if status not in ["pending", "approved", "rejected"]:
            raise HTTPException(
                status_code=400,
                detail="Status must be one of: pending, approved, rejected",
            )

        proposal_manager = get_proposal_manager()
        success = proposal_manager.update_proposal_status(
            proposal_id, status, review_notes
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Proposal '{proposal_id}' not found",
            )

        return {
            "proposal_id": proposal_id,
            "status": status,
            "message": "Proposal status updated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in update_proposal_status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update proposal: {str(e)}",
        )
