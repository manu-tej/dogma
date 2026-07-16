import type { GraphNode } from "../../lib/hypothesis-client";
import { useNodeGrounding } from "../../hooks/useNodeGrounding";
import { useNodeExpand } from "../../hooks/useNodeExpand";
import { ontologyTermUrl } from "../../lib/hypothesis-ui/sourceLinks";
import { Button } from "../ui/button";
import { NodeChatPanel } from "./NodeChatPanel";
import { ProposedEditCard } from "./ProposedEditCard";

interface NodePanelProps {
  node: GraphNode | null;
  graphId: string;
  onGraphChanged: () => void;
}

export function NodePanel({ node, graphId, onGraphChanged }: NodePanelProps) {
  if (!node) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
        Select a node to open its panel.
      </div>
    );
  }
  return (
    <NodePanelBody key={node.id} node={node} graphId={graphId} onGraphChanged={onGraphChanged} />
  );
}

function NodePanelBody({ node, graphId, onGraphChanged }: { node: GraphNode } & Omit<NodePanelProps, "node">) {
  const grounding = node.grounding ?? null;
  const isProteinState = grounding?.kind === "protein_state";
  // ontology_term display (de-doubled per f81ded8): "HP:0003240" stays, "P00533" -> "UniProt:P00533".
  const ontologyTerm = grounding?.kind === "ontology_term" ? grounding : null;
  const ontologyUrl = ontologyTerm
    ? ontologyTermUrl(ontologyTerm.ontology, ontologyTerm.term_id)
    : null;
  const ontologyLabel = ontologyTerm
    ? ontologyTerm.term_id.includes(":")
      ? ontologyTerm.term_id
      : `${ontologyTerm.ontology}:${ontologyTerm.term_id}`
    : null;
  const resolvedMember = isProteinState
    ? grounding.members.find((m) => m.term_id === grounding.resolved_to) ?? null
    : null;
  const { proposal, notFound, loading, applying, ground, accept, reject, resolveIsoform } =
    useNodeGrounding(graphId, node.id, onGraphChanged);
  const expand = useNodeExpand(graphId, node.id, onGraphChanged);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <h3 className="text-xs uppercase tracking-wide text-muted-foreground">Node</h3>
        <p className="text-lg font-medium text-foreground">{node.label}</p>
        <dl className="mt-2 space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Type</dt><dd className="font-mono text-foreground/90">{node.type}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Grounding</dt>
            <dd className="text-right font-mono text-foreground/90">
              {ontologyTerm ? (
                ontologyUrl ? (
                  <a href={ontologyUrl} target="_blank" rel="noopener noreferrer"
                     className="text-signal hover:underline" title={ontologyTerm.label ?? undefined}>
                    {ontologyLabel}
                  </a>
                ) : (
                  ontologyLabel
                )
              ) : isProteinState ? (
                <span className="text-foreground/90">{grounding.family_label}</span>
              ) : (
                "ungrounded"
              )}
            </dd>
          </div>
        </dl>
        {isProteinState && (
          <div className="mt-2 space-y-1 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-muted-foreground">Isoform</span>
              {resolvedMember ? (
                <>
                  <a
                    href={ontologyTermUrl(resolvedMember.ontology, resolvedMember.term_id) ?? undefined}
                    target="_blank" rel="noopener noreferrer"
                    className="font-mono text-signal hover:underline"
                    title={resolvedMember.term_id}
                  >
                    {resolvedMember.label ?? resolvedMember.term_id}
                  </a>
                  <Button size="sm" variant="ghost" className="text-muted-foreground"
                    disabled={applying} onClick={() => resolveIsoform(null)}>
                    × clear
                  </Button>
                </>
              ) : (
                <span className="flex flex-wrap gap-1">
                  {grounding.members.map((m) => (
                    <Button key={m.term_id} size="sm" variant="outline"
                      disabled={applying} onClick={() => resolveIsoform(m.term_id)}>
                      {m.label ?? m.term_id}
                    </Button>
                  ))}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Measurable as: direct (phospho-proteomics / RPPA) or an activity
              gene-signature (bulk RNA-seq).
            </p>
          </div>
        )}
        <Button
          size="sm"
          variant="ghost"
          className={`mt-2 ${node.grounding ? "text-muted-foreground" : "text-signal"}`}
          onClick={ground}
          disabled={loading}
        >
          {loading ? "Grounding…" : node.grounding ? "Re-ground" : "Ground to ontology"}
        </Button>
        {proposal?.proposed_edit && (
          <div className="mt-2">
            <ProposedEditCard edit={proposal.proposed_edit} applying={applying} onAccept={accept} onReject={reject} />
          </div>
        )}
        {notFound && (
          <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-300">
            {notFound}
            {node.type === "compound" && (
              <span className="mt-1 block text-amber-400/80">
                If this is a gene or protein, change its type to “target” (chat with the node), then ground again.
              </span>
            )}
          </div>
        )}
        <Button size="sm" variant="ghost" className="mt-2 ml-2 text-signal"
          onClick={expand.expand} disabled={expand.loading}>
          {expand.loading ? "Searching KG…" : "Expand from knowledge graph"}
        </Button>
        {expand.neighbors && (
          expand.neighbors.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">No knowledge-graph neighbors found.</p>
          ) : (
            <ul className="mt-2 space-y-1">
              {expand.neighbors.map((n) => (
                <li key={n.id}
                  className="elev-sm flex items-center justify-between rounded-md border border-border bg-surface-1 p-2 text-xs">
                  <span className="text-foreground/90">
                    <span className="font-mono font-medium text-foreground">{n.symbol}</span>{" "}
                    <span className="text-muted-foreground">{n.relation}</span>
                    <span className="font-mono text-muted-foreground/70"> · {n.sources.length} src</span>
                    {n.existing_node_id && <span className="text-signal/70"> · in graph</span>}
                  </span>
                  <Button size="sm" variant="outline" disabled={expand.adding === n.id}
                    onClick={() => expand.add(n)}>
                    {expand.adding === n.id
                      ? (n.existing_node_id ? "Connecting…" : "Adding…")
                      : (n.existing_node_id ? "Connect" : "Add")}
                  </Button>
                </li>
              ))}
            </ul>
          )
        )}
      </div>
      <NodeChatPanel graphId={graphId} nodeId={node.id} onApplied={onGraphChanged} />
    </div>
  );
}
