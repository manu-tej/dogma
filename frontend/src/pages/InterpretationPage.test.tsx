import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { InterpretationPage } from "./InterpretationPage";
import * as service from "../services/interpretationService";

vi.mock("../services/interpretationService", async (importOriginal) => {
  // Keep the real pure helpers (parseGeneTable/splitByDirection); stub the network call.
  const actual = await importOriginal<typeof service>();
  return { ...actual, interpretDEG: vi.fn() };
});

const mockResult: service.DEGInterpretation = {
  id: "deg-1",
  summary: "Estrogen signaling is elevated in treated vs control.",
  claims: [
    {
      claimType: "pathway",
      statement: "ESR1 upregulation activates estrogen response.",
      confidence: "high",
      genesMentioned: ["ESR1"],
      pathwaysMentioned: ["Estrogen signaling"],
      evidenceCount: 3,
    },
  ],
  toolCalls: [{ toolName: "reactome", status: "success", latencyMs: 120, cached: false }],
  openQuestions: ["Is GREB1 a direct target?"],
  limitations: ["Small sample size"],
  recommendations: ["Validate with qPCR"],
  confidenceScore: 0.82,
  tokenUsage: { inputTokens: 100, outputTokens: 200, totalTokens: 300 },
  costUsd: 0.0123,
  processingTimeMs: 4200,
  modelUsed: "claude-sonnet",
};

describe("InterpretationPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the example genes and shows the parsed up/down counts", () => {
    render(<InterpretationPage />);
    fireEvent.click(screen.getByText("Load example"));
    // Example has 3 up (ESR1, GREB1, EGFR) and 2 down (MKI67, CCNB1).
    expect(screen.getByText(/3 up/)).toBeInTheDocument();
    expect(screen.getByText(/2 down/)).toBeInTheDocument();
  });

  it("blocks submission without an upregulated gene", async () => {
    render(<InterpretationPage />);
    fireEvent.click(screen.getByRole("button", { name: /Interpret results/i }));
    expect(await screen.findByText(/at least one upregulated gene/i)).toBeInTheDocument();
    expect(service.interpretDEG).not.toHaveBeenCalled();
  });

  it("submits and renders the interpretation claims", async () => {
    vi.mocked(service.interpretDEG).mockResolvedValue(mockResult);
    render(<InterpretationPage />);
    fireEvent.click(screen.getByText("Load example"));
    fireEvent.click(screen.getByRole("button", { name: /Interpret results/i }));

    await waitFor(() =>
      expect(screen.getByText(/ESR1 upregulation activates estrogen response/)).toBeInTheDocument(),
    );
    expect(service.interpretDEG).toHaveBeenCalledOnce();
    expect(screen.getByText(/Estrogen signaling is elevated/)).toBeInTheDocument();
    expect(screen.getByText(/Validate with qPCR/)).toBeInTheDocument();
  });
});
