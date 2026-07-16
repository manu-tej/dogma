import { MethodBrowser } from "../components/MethodBrowser";
import { PageHeader } from "../components/PageHeader";

/** The analysis-method registry, rehomed from the previously-orphaned MethodBrowser. */
export function MethodsPage() {
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Methods"
        description="Browse the analysis-method registry and get recommendations for your task."
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <MethodBrowser />
      </div>
    </div>
  );
}
