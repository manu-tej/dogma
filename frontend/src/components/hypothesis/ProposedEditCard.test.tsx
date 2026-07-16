import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProposedEditCard } from "./ProposedEditCard";

describe("ProposedEditCard", () => {
  it("summarizes a split and fires accept/reject", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    render(<ProposedEditCard applying={false} onAccept={onAccept} onReject={onReject}
      edit={{ op: "split_edge", edge_id: "e1", mechanism_label: "KRAS",
              mechanism_type: "target", source_relation: "up-regulates", target_relation: "drives" }} />);
    expect(screen.getByText(/split/i)).toBeInTheDocument();
    expect(screen.getByText(/KRAS/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /accept/i }));
    expect(onAccept).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalled();
  });

  it("summarizes a flip", () => {
    render(<ProposedEditCard applying={false} onAccept={vi.fn()} onReject={vi.fn()}
      edit={{ op: "flip_edge", edge_id: "e1" }} />);
    expect(screen.getByText(/flip|reverse|direction/i)).toBeInTheDocument();
  });

  it("summarizes a node merge", () => {
    render(<ProposedEditCard applying={false} onAccept={vi.fn()} onReject={vi.fn()}
      edit={{ op: "merge_nodes", node_id: "B", into_node_id: "A" }} />);
    expect(screen.getByText(/merge/i)).toBeInTheDocument();
  });

  it("summarizes a node rename", () => {
    render(<ProposedEditCard applying={false} onAccept={vi.fn()} onReject={vi.fn()}
      edit={{ op: "set_label", node_id: "A", label: "ErbB1" }} />);
    expect(screen.getByText(/ErbB1/)).toBeInTheDocument();
  });

  it("summarizes a protein-state grounding edit", () => {
    render(
      <ProposedEditCard
        edit={{
          op: "set_protein_state_grounding",
          node_id: "n",
          family_label: "AKT (phospho-S473/T308)",
          members: [
            { kind: "ontology_term", ontology: "UniProt", term_id: "P31749", label: "AKT1" },
            { kind: "ontology_term", ontology: "UniProt", term_id: "P31751", label: "AKT2" },
          ],
          residues: ["S473", "T308"],
          resolved_to: null,
        }}
        applying={false}
        onAccept={() => {}}
        onReject={() => {}}
      />,
    );
    expect(screen.getByText(/AKT \(phospho-S473\/T308\)/)).toBeInTheDocument();
    expect(screen.getByText(/2 isoform/)).toBeInTheDocument();
  });
});
