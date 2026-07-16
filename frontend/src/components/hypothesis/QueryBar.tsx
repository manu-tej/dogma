import { Loader2, Search } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "../ui/button";
import { Input } from "../ui/input";

interface QueryBarProps {
  loading: boolean;
  onSubmit: (query: string) => void;
  /** Seed the field (e.g. carried over from the chat). */
  initialValue?: string;
  /** "lg" is the centered hero treatment; "md" is the slim top bar. */
  size?: "md" | "lg";
  /** When present, show a Re-roll button (regenerate the same query). */
  onReroll?: () => void;
}

export function QueryBar({ loading, onSubmit, initialValue = "", size = "md", onReroll }: QueryBarProps) {
  const [value, setValue] = useState(initialValue);
  const lg = size === "lg";

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (value.trim()) onSubmit(value.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="flex w-full items-center gap-2">
      <div className="relative flex-1">
        <Search
          className={`absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground ${lg ? "h-5 w-5" : "h-4 w-4"}`}
        />
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask a question, e.g. Does EGFR drive resistance to drugY in PhenotypeZ tumors?"
          className={`elev-sm border-border bg-surface-1 text-foreground placeholder:text-muted-foreground ${lg ? "h-14 text-base" : ""}`}
          // Inline so it beats the Input's base `px-3` and clears the search icon.
          style={{ paddingLeft: lg ? "2.75rem" : "2.25rem" }}
          aria-label="Hypothesis query"
          autoFocus={lg}
        />
      </div>
      <Button type="submit" disabled={loading || !value.trim()} size={lg ? "lg" : "default"}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Investigate"}
      </Button>
      {onReroll && (
        <Button
          type="button"
          variant="ghost"
          size={lg ? "lg" : "default"}
          disabled={loading}
          onClick={onReroll}
          title="Re-roll: regenerate a fresh hypothesis for the same question"
        >
          Re-roll
        </Button>
      )}
    </form>
  );
}
