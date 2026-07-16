import type { GraphEdit } from "../../lib/hypothesis-client";
import { Button } from "../ui/button";

function summarize(edit: GraphEdit): string {
  switch (edit.op) {
    case "set_relation":
      return `Rename the claim to "${edit.relation}".`;
    case "flip_edge":
      return "Flip the edge direction (reverse source and target).";
    case "set_test":
      return `Set the test${edit.pipeline ? ` — pipeline ${edit.pipeline}` : ""}${
        edit.data_accession ? ` on ${edit.data_accession}` : ""}.`;
    case "split_edge":
      return `Split the edge, inserting ${edit.mechanism_label} as the mechanism ` +
        `(${edit.source_relation} → ${edit.target_relation}).`;
    case "set_label":
      return `Rename this node to "${edit.label}".`;
    case "set_node_type":
      return `Change this node's type to ${edit.node_type}.`;
    case "set_grounding":
      return `Re-ground this node to ${edit.ontology}:${edit.term_id}.`;
    case "set_protein_state_grounding":
      return `Ground this node as the ${edit.family_label} family ` +
        `(${edit.members.length} isoform${edit.members.length === 1 ? "" : "s"}, phospho).`;
    case "resolve_isoform":
      return edit.resolved_to
        ? `Resolve the isoform to ${edit.resolved_to}.`
        : "Clear the isoform resolution.";
    case "merge_nodes":
      return "Merge this node into another (re-pointing its edges).";
    case "split_node":
      return `Split this node, moving ${edit.move_edge_ids.length} edge(s) to "${edit.new_label}".`;
    case "add_connected_node":
      return `Add "${edit.new_label}" (${edit.relation}) from the knowledge graph.`;
    case "connect_nodes":
      return `Add a ${edit.relation} edge from the knowledge graph.`;
    default:
      return "Proposed change.";
  }
}

interface ProposedEditCardProps {
  edit: GraphEdit;
  applying: boolean;
  onAccept: () => void;
  onReject: () => void;
}

export function ProposedEditCard({ edit, applying, onAccept, onReject }: ProposedEditCardProps) {
  return (
    <div className="trace-band elev rounded-lg border border-signal/40 bg-surface-2 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-signal">Proposed change</p>
      <p className="mb-3 text-sm text-foreground/90">{summarize(edit)}</p>
      <div className="flex gap-2">
        <Button size="sm" onClick={onAccept} disabled={applying}>
          {applying ? "Applying…" : "Accept"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onReject} disabled={applying}
          className="text-muted-foreground">Reject</Button>
      </div>
    </div>
  );
}
