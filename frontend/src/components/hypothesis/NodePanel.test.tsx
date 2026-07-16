import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const groundNode = vi.fn();
const applyEdit = vi.fn();
vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() { return { nodeChat: vi.fn(), applyEdit, groundNode }; },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), message: vi.fn() } }));

import { NodePanel } from "./NodePanel";

const node = { id: "P00533", type: "target" as const, label: "EGFR",
  grounding: { kind: "ontology_term" as const, ontology: "UniProt", term_id: "P00533", label: "EGFR" } };
const ungrounded = { id: "n1", type: "target" as const, label: "EGFR", grounding: null };

const PROTEIN_STATE_NODE = {
  id: "n",
  type: "phenotype" as const,
  label: "pAKT (phospho-AKT; S473/T308)",
  grounding: {
    kind: "protein_state" as const,
    family_label: "AKT (phospho-S473/T308)",
    members: [
      { kind: "ontology_term" as const, ontology: "UniProt", term_id: "P31749", label: "AKT1" },
      { kind: "ontology_term" as const, ontology: "UniProt", term_id: "P31751", label: "AKT2" },
      { kind: "ontology_term" as const, ontology: "UniProt", term_id: "Q9Y243", label: "AKT3" },
    ],
    modification: { kind: "phosphorylation" as const, residues: ["S473", "T308"] },
    resolved_to: null,
  },
};

describe("NodePanel", () => {
  it("empty state when no node", () => {
    render(<NodePanel node={null} graphId="g1" onGraphChanged={vi.fn()} />);
    expect(screen.getByText(/select a node/i)).toBeInTheDocument();
  });

  it("renders node attributes + the chat", () => {
    render(<NodePanel node={node} graphId="g1" onGraphChanged={vi.fn()} />);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText(/target/)).toBeInTheDocument();
    expect(screen.getByText(/UniProt:P00533/)).toBeInTheDocument();
    expect(screen.getByText(/chat with this node/i)).toBeInTheDocument();
  });

  it("ground button looks up a term, shows the proposal, and applies on accept", async () => {
    groundNode.mockResolvedValue({
      found: true, summary: "matched",
      proposed_edit: { op: "set_grounding", node_id: "n1", ontology: "UniProt", term_id: "P00533" },
    });
    applyEdit.mockResolvedValue({ id: "g1", query: "q", nodes: [], edges: [] });
    const onGraphChanged = vi.fn();
    render(<NodePanel node={ungrounded} graphId="g1" onGraphChanged={onGraphChanged} />);

    fireEvent.click(screen.getByRole("button", { name: /ground/i }));
    await waitFor(() => expect(groundNode).toHaveBeenCalledWith("g1", "n1"));
    const accept = await screen.findByRole("button", { name: /accept/i });
    fireEvent.click(accept);
    await waitFor(() => expect(applyEdit).toHaveBeenCalled());
    expect(onGraphChanged).toHaveBeenCalled();
  });

  it("renders a protein-state family with an isoform picker and the advisory line", () => {
    render(<NodePanel node={PROTEIN_STATE_NODE} graphId="g" onGraphChanged={() => {}} />);
    expect(screen.getByText(/AKT \(phospho-S473\/T308\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AKT1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AKT3" })).toBeInTheDocument();
    expect(screen.getByText(/Measurable as/i)).toBeInTheDocument();
  });

  it("renders the resolved isoform with a clear control", () => {
    const resolved = {
      ...PROTEIN_STATE_NODE,
      grounding: { ...PROTEIN_STATE_NODE.grounding, resolved_to: "P31751" },
    };
    render(<NodePanel node={resolved} graphId="g" onGraphChanged={() => {}} />);
    expect(screen.getByText("AKT2")).toBeInTheDocument();           // chosen member shown
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "AKT1" })).not.toBeInTheDocument(); // picker hidden
  });

  it("renders an ontology_term grounding unchanged (single CURIE, no advisory)", () => {
    const node = {
      id: "n", type: "target" as const, label: "EGFR",
      grounding: { kind: "ontology_term" as const, ontology: "UniProt", term_id: "P00533", label: "EGFR" },
    };
    render(<NodePanel node={node} graphId="g" onGraphChanged={() => {}} />);
    expect(screen.getByText("UniProt:P00533")).toBeInTheDocument();
    expect(screen.queryByText(/Measurable as/i)).not.toBeInTheDocument();
  });

  it("clicking an isoform applies a resolve_isoform edit and refreshes", async () => {
    applyEdit.mockResolvedValue({ id: "g", query: "q", nodes: [], edges: [] });
    const onGraphChanged = vi.fn();
    render(<NodePanel node={PROTEIN_STATE_NODE} graphId="g" onGraphChanged={onGraphChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "AKT2" }));
    await waitFor(() =>
      expect(applyEdit).toHaveBeenCalledWith("g", {
        op: "resolve_isoform", node_id: "n", resolved_to: "P31751",
      }));
    expect(onGraphChanged).toHaveBeenCalled();
  });

  it("clicking clear applies a resolve_isoform edit with resolved_to null", async () => {
    applyEdit.mockResolvedValue({ id: "g", query: "q", nodes: [], edges: [] });
    const resolved = {
      ...PROTEIN_STATE_NODE,
      grounding: { ...PROTEIN_STATE_NODE.grounding, resolved_to: "P31751" },
    };
    render(<NodePanel node={resolved} graphId="g" onGraphChanged={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    await waitFor(() =>
      expect(applyEdit).toHaveBeenCalledWith("g", {
        op: "resolve_isoform", node_id: "n", resolved_to: null,
      }));
  });
});
