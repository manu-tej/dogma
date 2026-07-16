import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { demoProposal } from "../../lib/hypothesis-ui/fixtures";
import { CheckpointCard } from "./CheckpointCard";

describe("CheckpointCard", () => {
  it("renders the gap and pipeline and fires onApprove with the proposal", () => {
    const onApprove = vi.fn();
    render(
      <CheckpointCard proposal={demoProposal} running={false}
        onApprove={onApprove} onSkip={vi.fn()} />,
    );
    expect(screen.getByText(/no experimental evidence yet/i)).toBeInTheDocument();
    expect(screen.getByText("nf-core/rnaseq")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onApprove).toHaveBeenCalledWith(demoProposal);
  });

  it("disables buttons while running", () => {
    render(
      <CheckpointCard proposal={demoProposal} running={true}
        onApprove={vi.fn()} onSkip={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /executing|approve/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /skip/i })).toBeDisabled();
  });

  it("Adjust reveals editable pipeline/data and approves with edited values", () => {
    const onApprove = vi.fn();
    render(
      <CheckpointCard proposal={demoProposal} running={false}
        onApprove={onApprove} onSkip={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /adjust/i }));
    const pipeline = screen.getByLabelText(/pipeline/i);
    fireEvent.change(pipeline, { target: { value: "nf-core/differentialabundance" } });
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onApprove).toHaveBeenCalledWith(
      expect.objectContaining({ pipeline: "nf-core/differentialabundance", data_accession: "GSE-DEMO" }),
    );
  });

  it("renders the broker recommendation label when method is present", () => {
    const withMethod = {
      ...demoProposal,
      method: {
        method_id: "deseq2", name: "DESeq2", score: 0.713,
        source: "structural" as const, rationale: "fits rna_seq",
      },
    };
    render(
      <CheckpointCard proposal={withMethod} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()} />,
    );
    expect(screen.getByText(/recommended:/i)).toBeInTheDocument();
    expect(screen.getByText(/DESeq2/)).toBeInTheDocument();
    expect(screen.getByText(/0\.71/)).toBeInTheDocument();
  });

  it("omits the recommendation label when method is absent", () => {
    render(
      <CheckpointCard proposal={demoProposal} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()} />,
    );
    expect(screen.queryByText(/recommended:/i)).not.toBeInTheDocument();
  });

  it("shows the Graph grounding panel when method.grounding is present", () => {
    const withGrounding = {
      ...demoProposal,
      method: {
        method_id: "m:salmon", name: "salmon", score: 0.81,
        source: "structural" as const, rationale: "fits rna_seq",
        grounding: "# salmon neighborhood\n- assumes X",
      },
    };
    render(
      <CheckpointCard proposal={withGrounding} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()} />,
    );
    expect(screen.getByText(/Method grounding/)).toBeInTheDocument();
    expect(screen.getByText(/describes the method, not specific to this edge/)).toBeInTheDocument();
    expect(screen.getByText(/salmon neighborhood/)).toBeInTheDocument();
  });

  it("hides the Graph grounding panel when method has no grounding", () => {
    const noGrounding = {
      ...demoProposal,
      method: {
        method_id: "deseq2", name: "DESeq2", score: 0.7,
        source: "structural" as const, rationale: "fits rna_seq",
      },
    };
    render(
      <CheckpointCard proposal={noGrounding} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()} />,
    );
    expect(screen.queryByText(/Method grounding/)).not.toBeInTheDocument();
  });

  it("escapes HTML in the grounding blob (no DOM injection)", () => {
    const payload = '<img src=x onerror="boom"><script>1</script><b>x</b>';
    const withXss = {
      ...demoProposal,
      method: {
        method_id: "m", name: "m", score: 0.5,
        source: "structural" as const, rationale: "r", grounding: payload,
      },
    };
    const { container } = render(
      <CheckpointCard proposal={withXss} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    // rendered verbatim as escaped text inside the <pre>
    expect(container.querySelector("pre")?.textContent).toBe(payload);
  });
});
