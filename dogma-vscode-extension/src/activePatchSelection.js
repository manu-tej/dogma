"use strict";

function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/").replace(/^\.\//, "");
}

function activeFilePatchProposals(result = {}, activePath = "") {
  const normalizedActivePath = normalizePath(activePath);
  if (!normalizedActivePath) return [];

  return (result.proposals || []).filter((proposal) => {
    const target = normalizePath(proposal.target_file);
    return target === normalizedActivePath || target.endsWith(`/${normalizedActivePath}`);
  });
}

module.exports = {
  activeFilePatchProposals,
  normalizePath
};
