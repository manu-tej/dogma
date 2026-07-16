import type { EvidenceEntry, GraphEdge, ProposedTest } from "../../lib/hypothesis-client";
import { CheckpointCard } from "./CheckpointCard";
import { EdgeChatPanel } from "./EdgeChatPanel";
import { EvidenceLedger } from "./EvidenceLedger";
import { FindDatasets } from "./FindDatasets";
import { KgKnowledgePanel } from "./KgKnowledgePanel";
import { MethodGroundingPanel, type MethodGroundingPanelProps } from "./MethodGroundingPanel";
import { evidenceFacts, factsSummaryLine } from "../../lib/hypothesis-ui/evidence-facts";

interface EdgeDossierProps {
  edge: GraphEdge | null;
  sourceLabel: string;
  targetLabel: string;
  evidence: EvidenceEntry[];
  proposal: ProposedTest | null;
  running: boolean;
  onApprove: (proposed: ProposedTest) => void;
  onSkip: () => void;
  graphId: string;
  onGraphChanged: () => void;
}

export function EdgeDossier({
  edge, sourceLabel, targetLabel, evidence, proposal, running, onApprove, onSkip,
  graphId, onGraphChanged,
}: EdgeDossierProps) {
  if (!edge) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground/70">
        Select an edge to open its dossier.
      </div>
    );
  }

  const mgEntry = [...evidence].reverse().find(
    (e) => e.provenance?.kind === "pipeline_run" && e.provenance.data_accession === "methods-graph",
  );

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <h3 className="text-xs uppercase tracking-wide text-muted-foreground/70">Claim</h3>
        <p className="text-foreground">
          <span className="font-medium">{sourceLabel}</span>{" "}
          <span className="text-muted-foreground">{edge.relation}</span>{" "}
          <span className="font-medium">{targetLabel}</span>
        </p>
      </div>

      <p className="text-sm text-muted-foreground">{factsSummaryLine(evidenceFacts(evidence))}</p>
      <KgKnowledgePanel
        key={`kg-${edge.id}`}
        graphId={graphId}
        edgeId={edge.id}
        suggestedBy={edge.suggested_by}
      />
      <EvidenceLedger entries={evidence} />
      {mgEntry && (
        <MethodGroundingPanel
          verdict={(mgEntry.magnitude as MethodGroundingPanelProps["verdict"]) ?? "COVERAGE_GAP"}
          summary={mgEntry.rationale ?? ""}
        />
      )}

      {proposal ? (
        <CheckpointCard proposal={proposal} running={running}
          onApprove={onApprove} onSkip={onSkip} />
      ) : (
        <p className="text-xs text-muted-foreground/70">
          This edge is not the current focus. Approve the proposed edge to advance the loop.
        </p>
      )}
      <FindDatasets key={`data-${edge.id}`} graphId={graphId} edgeId={edge.id} onAttached={onGraphChanged} />
      <EdgeChatPanel key={edge.id} graphId={graphId} edgeId={edge.id} onApplied={onGraphChanged} />
    </div>
  );
}
