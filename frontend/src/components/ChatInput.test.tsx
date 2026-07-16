import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "./ChatInput";

// The real composer is Lexical (contenteditable), which jsdom can't drive via
// fireEvent.change. Mock it with a plain textarea stand-in so we can unit-test
// ChatInput's own logic (the hypothesis affordance). Lexical is verified live.
vi.mock("./RichTextInput", () => ({
  RichTextInput: React.forwardRef(function MockRichTextInput(
    props: {
      onChange?: (t: string) => void;
      onSubmit?: () => void;
      placeholder?: string;
      disabled?: boolean;
      ariaLabel?: string;
    },
    ref: React.Ref<{ clear: () => void; focus: () => void }>,
  ) {
    React.useImperativeHandle(ref, () => ({ clear: () => {}, focus: () => {} }));
    return (
      <textarea
        aria-label={props.ariaLabel}
        placeholder={props.placeholder}
        disabled={props.disabled}
        onChange={(e) => props.onChange?.(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            props.onSubmit?.();
          }
        }}
      />
    );
  }),
}));

describe("ChatInput hypothesis affordance", () => {
  it("offers 'Investigate as a hypothesis' once there is text, carrying it over", () => {
    const onOpenHypothesis = vi.fn();
    render(<ChatInput onSendMessage={vi.fn()} onOpenHypothesis={onOpenHypothesis} />);

    // Hidden while the input is empty.
    expect(screen.queryByRole("button", { name: /investigate as a hypothesis/i })).toBeNull();

    const box = screen.getByPlaceholderText(/Search for RNA-Seq datasets/i);
    fireEvent.change(box, { target: { value: "Does EGFR drive resistance?" } });

    const cta = screen.getByRole("button", { name: /investigate as a hypothesis/i });
    fireEvent.click(cta);
    expect(onOpenHypothesis).toHaveBeenCalledWith("Does EGFR drive resistance?");
  });

  it("does not render the affordance when no handler is provided", () => {
    render(<ChatInput onSendMessage={vi.fn()} />);
    const box = screen.getByPlaceholderText(/Search for RNA-Seq datasets/i);
    fireEvent.change(box, { target: { value: "anything" } });
    expect(screen.queryByRole("button", { name: /investigate as a hypothesis/i })).toBeNull();
  });

  it("sends on Enter via the composer and reports the text", () => {
    const onSendMessage = vi.fn();
    render(<ChatInput onSendMessage={onSendMessage} />);
    const box = screen.getByPlaceholderText(/Search for RNA-Seq datasets/i);
    fireEvent.change(box, { target: { value: "mouse liver RNA-seq" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSendMessage).toHaveBeenCalledWith("mouse liver RNA-seq");
  });
});
