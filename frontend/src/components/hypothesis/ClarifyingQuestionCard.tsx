import { type FormEvent, useState } from "react";

import type { ClarifyingQuestion, SeedAnswer } from "../../lib/hypothesis-client";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

interface ClarifyingQuestionCardProps {
  question: ClarifyingQuestion;
  onAnswer: (answer: SeedAnswer) => void;
}

export function ClarifyingQuestionCard({ question, onAnswer }: ClarifyingQuestionCardProps) {
  const [text, setText] = useState("");
  const emit = (value: string) => onAnswer({ question_id: question.id, value });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) emit(text.trim());
  };

  return (
    <div className="elev rounded-lg border border-border bg-card p-4">
      <p className="mb-3 text-foreground">{question.prompt}</p>
      <div className="mb-3 flex flex-wrap gap-2">
        {question.suggestions.map((s) => (
          <Button key={s} size="sm" variant="outline"
            className="border-border bg-surface-2 text-foreground/90 hover:border-signal/50 hover:text-signal"
            onClick={() => emit(s)}>
            {s}
          </Button>
        ))}
      </div>
      {question.allow_free_text && (
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Or type your own…"
            aria-label="Your answer"
            className="border-border bg-surface-2 text-foreground placeholder:text-muted-foreground/70"
          />
          <Button type="submit" disabled={!text.trim()}>Submit</Button>
        </form>
      )}
    </div>
  );
}
