"use strict";

function safePatchUriPart(value) {
  return encodeURIComponent(String(value || "patch").replace(/[^A-Za-z0-9_.-]+/g, "-"));
}

function patchDiffTitle(proposal) {
  return `Dogma Patch Preview: ${(proposal && (proposal.target_file || proposal.id)) || "proposal"}`;
}

function patchDiffDocumentContents(proposal) {
  return {
    before: (proposal && proposal.before) || "",
    after: (proposal && proposal.after) || ""
  };
}

module.exports = {
  patchDiffDocumentContents,
  patchDiffTitle,
  safePatchUriPart
};
