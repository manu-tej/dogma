"use strict";

function proposalQuickPickItems(result) {
  return (result.proposals || []).map((proposal) => ({
    label: proposal.title || proposal.id || "Dogma patch proposal",
    description: [proposal.kind, proposal.target_file].filter(Boolean).join(" • "),
    detail: proposal.rationale || proposal.id || "Review-first Dogma patch proposal.",
    proposalId: proposal.id,
    proposal
  }));
}

function selectedProposalId(item) {
  return item?.proposalId || item?.proposal?.id;
}

module.exports = {
  proposalQuickPickItems,
  selectedProposalId
};
