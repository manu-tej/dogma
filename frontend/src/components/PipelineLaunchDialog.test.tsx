import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { PipelineLaunchDialog } from "./PipelineLaunchDialog";
import { pipelineClient } from "../lib/pipeline-client";

vi.mock("../lib/pipeline-client", () => ({
  pipelineClient: { executePipeline: vi.fn() },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const pipeline: any = {
  id: "nf-core/rnaseq",
  name: "rnaseq",
  version: "3.14.0",
  parameters: [
    { name: "genome", type: "string", description: "Reference genome", required: true, group: "main" },
    { name: "skip_qc", type: "boolean", description: "Skip QC", required: false, group: "qc" },
  ],
};

describe("PipelineLaunchDialog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders required parameters and the samplesheet field", () => {
    render(<PipelineLaunchDialog pipeline={pipeline} open onOpenChange={vi.fn()} onLaunched={vi.fn()} />);
    expect(screen.getByText("Launch rnaseq")).toBeInTheDocument();
    expect(screen.getByText("genome")).toBeInTheDocument(); // required param
    expect(screen.queryByText("skip_qc")).not.toBeInTheDocument(); // optional, not shown
  });

  it("requires a samplesheet before launching", async () => {
    render(<PipelineLaunchDialog pipeline={pipeline} open onOpenChange={vi.fn()} onLaunched={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Launch run/i }));
    expect(await screen.findByText(/samplesheet path or URL is required/i)).toBeInTheDocument();
    expect(pipelineClient.executePipeline).not.toHaveBeenCalled();
  });

  it("launches with the configured input and calls onLaunched", async () => {
    vi.mocked(pipelineClient.executePipeline).mockResolvedValue({
      execution_id: "exec-1",
      pipeline_id: pipeline.id,
      status: "pending" as any,
      message: "ok",
      output_directory: "/out",
    });
    const onLaunched = vi.fn();
    const onOpenChange = vi.fn();
    render(<PipelineLaunchDialog pipeline={pipeline} open onOpenChange={onOpenChange} onLaunched={onLaunched} />);

    fireEvent.change(screen.getByPlaceholderText(/samplesheet.csv/i), {
      target: { value: "/data/sheet.csv" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Launch run/i }));

    await waitFor(() => expect(onLaunched).toHaveBeenCalledWith("exec-1"));
    const req = vi.mocked(pipelineClient.executePipeline).mock.calls[0][0];
    expect(req.pipeline_id).toBe("nf-core/rnaseq");
    expect(req.input_spec.samplesheet).toBe("/data/sheet.csv");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
