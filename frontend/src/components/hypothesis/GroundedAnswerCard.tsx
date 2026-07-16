import { Button } from "../ui/button";

interface GroundedAnswerCardProps {
  query: string;
  onEscalate: () => void;
}

export function GroundedAnswerCard({ query, onEscalate }: GroundedAnswerCardProps) {
  return (
    <div className="elev mx-auto mt-8 max-w-2xl rounded-lg border border-border bg-card p-4 animate-in fade-in slide-in-from-bottom-2">
      <h3 className="text-xs uppercase tracking-wide text-muted-foreground">Grounded answer</h3>
      <p className="mt-1 text-sm text-foreground/90">
        Your question <span className="text-foreground">"{query}"</span> was triaged as a simple,
        factual lookup. Grounded answers carry provenance (ontology / KG / literature) and are
        rendered here.
      </p>
      <Button className="mt-3" size="sm" variant="outline" onClick={onEscalate}>
        Investigate as a hypothesis →
      </Button>
    </div>
  );
}
