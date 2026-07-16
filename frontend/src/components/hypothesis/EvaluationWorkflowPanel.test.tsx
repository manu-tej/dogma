import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvaluationWorkflowPanel } from "./EvaluationWorkflowPanel";

const noop = () => Promise.reject(new Error("not called"));

describe("EvaluationWorkflowPanel", () => {
  it("prompts to select an edge when none is given", () => {
    render(
      <EvaluationWorkflowPanel
        edge={null}
        targetLabel=""
        getPlan={noop}
        onResolve={noop}
      />,
    );
    expect(screen.getByText(/select an edge/i)).toBeInTheDocument();
  });
});
