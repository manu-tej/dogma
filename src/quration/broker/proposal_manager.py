"""
Proposal Manager

Manages user proposals for new methods to be added to the registry.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from quration.broker.models import MethodProposal


class ProposalManager:
    """
    Manages method proposals from users.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize the proposal manager.

        Args:
            storage_path: Path to store proposals (JSON file)
        """
        self.storage_path = storage_path or Path("data/method_proposals.json")
        self.proposals: Dict[str, MethodProposal] = {}

        # Load existing proposals
        if self.storage_path.exists():
            self.load_proposals()

    def submit_proposal(self, proposal: MethodProposal) -> str:
        """
        Submit a new method proposal.

        Args:
            proposal: MethodProposal to submit

        Returns:
            Proposal ID
        """
        # Generate unique ID
        proposal_id = f"proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.proposals)}"

        # Store proposal
        self.proposals[proposal_id] = proposal

        # Save to disk
        self.save_proposals()

        return proposal_id

    def get_proposal(self, proposal_id: str) -> Optional[MethodProposal]:
        """
        Retrieve a proposal by ID.

        Args:
            proposal_id: Proposal identifier

        Returns:
            MethodProposal if found, None otherwise
        """
        return self.proposals.get(proposal_id)

    def list_proposals(
        self,
        status: Optional[str] = None,
        proposed_by: Optional[str] = None,
    ) -> List[MethodProposal]:
        """
        List proposals with optional filtering.

        Args:
            status: Filter by status (pending, approved, rejected)
            proposed_by: Filter by user

        Returns:
            List of matching proposals
        """
        proposals = list(self.proposals.values())

        if status:
            proposals = [p for p in proposals if p.status == status]

        if proposed_by:
            proposals = [p for p in proposals if p.proposed_by == proposed_by]

        # Sort by date (newest first)
        proposals.sort(key=lambda p: p.proposed_at, reverse=True)

        return proposals

    def update_proposal_status(
        self,
        proposal_id: str,
        status: str,
        review_notes: Optional[str] = None,
    ) -> bool:
        """
        Update the status of a proposal.

        Args:
            proposal_id: Proposal identifier
            status: New status (pending, approved, rejected)
            review_notes: Optional review notes

        Returns:
            True if successful, False otherwise
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False

        proposal.status = status
        if review_notes:
            proposal.review_notes = review_notes

        self.save_proposals()
        return True

    def get_proposal_stats(self) -> Dict[str, any]:
        """
        Get statistics about proposals.

        Returns:
            Dictionary with proposal statistics
        """
        proposals = list(self.proposals.values())

        return {
            "total_proposals": len(proposals),
            "by_status": {
                "pending": len([p for p in proposals if p.status == "pending"]),
                "approved": len([p for p in proposals if p.status == "approved"]),
                "rejected": len([p for p in proposals if p.status == "rejected"]),
            },
            "recent_proposals": len(
                [
                    p
                    for p in proposals
                    if (datetime.now() - p.proposed_at).days <= 30
                ]
            ),
        }

    def save_proposals(self):
        """Save proposals to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            proposal_id: proposal.model_dump(mode="json")
            for proposal_id, proposal in self.proposals.items()
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load_proposals(self):
        """Load proposals from disk."""
        with open(self.storage_path) as f:
            data = json.load(f)

        for proposal_id, proposal_data in data.items():
            proposal = MethodProposal(**proposal_data)
            self.proposals[proposal_id] = proposal
