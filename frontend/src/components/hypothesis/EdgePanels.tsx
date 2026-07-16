import { useState, type ReactNode } from "react";
import { EdgeDossier } from "./EdgeDossier";
import { EvaluationWorkflowPanel } from "./EvaluationWorkflowPanel";
import { cn } from "../ui/utils";
import type { EvidenceEntry, GraphEdge, ProposedTest } from "../../lib/hypothesis-client";
import { hypothesisClient } from "../../services/hypothesisService";

export interface EdgePanelsProps {
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

type Tab = "workflow" | "dossier";

/**
 * The right-side panel for a selected edge. The agent-planned EvaluationWorkflowPanel
 * is the dominant, default view (the edge opening into its own workflow graph); the
 * EdgeDossier — claim, KG knowledge, datasets, edge chat, evidence ledger — lives one
 * tab over, so the real grounding tools stay reachable without crowding the workflow.
 */
export function EdgePanels(props: EdgePanelsProps) {
  const [tab, setTab] = useState<Tab>("workflow");

  if (!props.edge) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
        Select an edge to open its evaluation workflow.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 gap-1 border-b border-border px-3 pt-2">
        <TabButton active={tab === "workflow"} onClick={() => setTab("workflow")}>
          Workflow
        </TabButton>
        <TabButton active={tab === "dossier"} onClick={() => setTab("dossier")}>
          Dossier
        </TabButton>
      </div>
      <div className="min-h-0 flex-1">
        {tab === "workflow" ? (
          <EvaluationWorkflowPanel
            edge={props.edge}
            sourceLabel={props.sourceLabel}
            targetLabel={props.targetLabel}
            getPlan={(id) => hypothesisClient.getEvaluationPlan(props.graphId, id)}
            onResolve={(id) => hypothesisClient.resolveReadout(props.graphId, id)}
          />
        ) : (
          <EdgeDossier {...props} />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "-mb-px rounded-t-md border-b-2 px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-signal text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground/90",
      )}
    >
      {children}
    </button>
  );
}
