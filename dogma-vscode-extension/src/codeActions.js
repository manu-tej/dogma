"use strict";

const SAMPLE_VALIDATION_MESSAGE = "Nextflow sample sheet rows should be validated before file tuple creation.";

const SERVICE_PATCH_BY_CODE = {
  "nextflow.sample_sheet_validation": {
    proposalId: "nextflow-sample-validation-1",
    label: "sample-sheet validation"
  },
  "metadata.missing_sample_id_policy": {
    proposalId: "metadata-sample-id-policy-1",
    label: "sample identifier policy"
  }
};

function actionKindForDiagnostic(diagnostic) {
  if (diagnostic.source !== "Dogma") return null;
  if (diagnostic.message === SAMPLE_VALIDATION_MESSAGE) return "sampleValidationPatch";
  if (diagnostic.code && SERVICE_PATCH_BY_CODE[String(diagnostic.code)]) return "servicePatchProposal";
  return null;
}

function actionTitle(kind) {
  if (kind === "sampleValidationPatch") {
    return "Dogma: insert sample-sheet validation helper";
  }
  return null;
}

function servicePatchDescriptor(diagnostic, mode) {
  const mapped = SERVICE_PATCH_BY_CODE[String(diagnostic.code || "")];
  if (!mapped) return null;
  const verb = mode === "apply" ? "apply" : "preview";
  return {
    kind: `servicePatch.${mode}`,
    title: `Dogma: ${verb} local service patch for ${mapped.label}`,
    command: mode === "apply" ? "dogma.applyServicePatchProposal" : "dogma.previewServicePatchProposal",
    proposalId: mapped.proposalId,
    isPreferred: mode === "preview"
  };
}

function codeActionDescriptors(diagnostics) {
  const seen = new Set();
  const actions = [];

  for (const diagnostic of diagnostics) {
    const kind = actionKindForDiagnostic(diagnostic);
    if (!kind) continue;

    if (kind === "servicePatchProposal") {
      for (const mode of ["preview", "apply"]) {
        const descriptor = servicePatchDescriptor(diagnostic, mode);
        const key = `${descriptor?.kind}:${descriptor?.proposalId}`;
        if (descriptor && !seen.has(key)) {
          actions.push(descriptor);
          seen.add(key);
        }
      }
      continue;
    }

    if (seen.has(kind)) continue;
    const title = actionTitle(kind);
    if (title) {
      actions.push({ kind, title, command: "dogma.applySampleValidationPatch", isPreferred: true });
      seen.add(kind);
    }
  }

  return actions;
}

module.exports = {
  SAMPLE_VALIDATION_MESSAGE,
  SERVICE_PATCH_BY_CODE,
  actionKindForDiagnostic,
  actionTitle,
  codeActionDescriptors,
  servicePatchDescriptor
};
