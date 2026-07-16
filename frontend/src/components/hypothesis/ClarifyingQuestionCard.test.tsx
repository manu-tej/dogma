import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ClarifyingQuestionCard } from "./ClarifyingQuestionCard";

const question = {
  id: "context", prompt: "Which cancer context?",
  suggestions: ["lung", "colorectal"], allow_free_text: true,
};

describe("ClarifyingQuestionCard", () => {
  it("answers via a chip", () => {
    const onAnswer = vi.fn();
    render(<ClarifyingQuestionCard question={question} onAnswer={onAnswer} />);
    expect(screen.getByText("Which cancer context?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "lung" }));
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "context", value: "lung" });
  });

  it("answers via free text", () => {
    const onAnswer = vi.fn();
    render(<ClarifyingQuestionCard question={question} onAnswer={onAnswer} />);
    fireEvent.change(screen.getByLabelText(/your answer/i), { target: { value: "pancreatic" } });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    expect(onAnswer).toHaveBeenCalledWith({ question_id: "context", value: "pancreatic" });
  });
});
