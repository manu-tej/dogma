import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const findData = vi.fn();
const applyEdit = vi.fn();
vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() { return { findData, applyEdit }; },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

import { FindDatasets } from "./FindDatasets";

describe("FindDatasets", () => {
  it("searches, lists candidates, and attaches a pick as a set_test", async () => {
    findData.mockResolvedValue([
      { source: "geo", accession: "GSE-TEST", title: "test fixture candidate",
        organism: "Homo sapiens", n_samples: 6, suggested_pipeline: "nf-core/differentialabundance" },
    ]);
    applyEdit.mockResolvedValue({ id: "g1", query: "q", nodes: [], edges: [] });
    const onAttached = vi.fn();
    render(<FindDatasets graphId="g1" edgeId="e1" onAttached={onAttached} />);

    fireEvent.click(screen.getByRole("button", { name: /find datasets/i }));
    await waitFor(() => expect(findData).toHaveBeenCalledWith("g1", "e1"));
    expect(await screen.findByText("GSE-TEST")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /attach as test/i }));
    await waitFor(() => expect(applyEdit).toHaveBeenCalled());
    const [, edit] = applyEdit.mock.calls[0];
    expect(edit).toMatchObject({ op: "set_test", edge_id: "e1", data_accession: "GSE-TEST",
      pipeline: "nf-core/differentialabundance" });
    expect(onAttached).toHaveBeenCalled();
  });

  it("shows an empty-state when no datasets are found", async () => {
    findData.mockResolvedValue([]);
    render(<FindDatasets graphId="g1" edgeId="e1" onAttached={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /find datasets/i }));
    expect(await screen.findByText(/no datasets found/i)).toBeInTheDocument();
  });

  it("labels an offline candidate as synthetic rather than public GEO evidence", async () => {
    findData.mockResolvedValue([
      {
        source: "geo",
        accession: "GSE-DEMO",
        title: "Synthetic offline dataset candidate (not a GEO result)",
        match_reasons: ["synthetic demo; not returned by a live GEO search"],
      },
    ]);
    render(<FindDatasets graphId="g1" edgeId="e1" onAttached={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /find datasets/i }));
    expect(await screen.findByText("synthetic demo")).toBeInTheDocument();
    expect(screen.getByText(/not a live public-dataset result/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /attach synthetic demo/i })).toBeInTheDocument();
  });
});
