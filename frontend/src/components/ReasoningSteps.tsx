import { useState } from 'react';
import { CheckCircle2, Circle, Loader2, Search, Database, Filter, ClipboardList, ChevronDown, ChevronRight } from 'lucide-react';
import * as Collapsible from '@radix-ui/react-collapsible';
import { QuerySyntaxHighlighter } from './QuerySyntaxHighlighter';

interface ReasoningStep {
  id: string;
  type: 'query_generation' | 'ncbi_search' | 'metadata_fetch' | 'filtering' | 'results';
  title: string;
  description: string;
  status: 'pending' | 'running' | 'complete';
  data?: any;
  progress?: number;
  total?: number;
}

interface ReasoningStepsProps {
  steps: ReasoningStep[];
}

const stepIcons = {
  query_generation: ClipboardList,  // Generating search queries
  ncbi_search: Database,            // Searching NCBI GEO
  metadata_fetch: Search,           // Fetching dataset metadata
  filtering: Filter,                 // Filtering & ranking
  results: CheckCircle2             // Search complete
};

// Helper function to render step-specific detailed data
function renderStepDetails(step: ReasoningStep) {
  if (!step.data) return null;

  switch (step.type) {
    case 'query_generation':
      return (
        <div className="mt-2 pt-2 border-t border-border space-y-1">
          {step.data.query_count && (
            <p className="text-xs text-muted-foreground">
              • Generated {step.data.query_count} search {step.data.query_count === 1 ? 'query' : 'queries'}
            </p>
          )}
          {step.data.queries && Array.isArray(step.data.queries) && (
            <div className="space-y-2 ml-2">
              {step.data.queries.slice(0, 5).map((query: string, idx: number) => (
                <div key={idx} className="text-xs">
                  <span className="text-muted-foreground/70">Query {idx + 1}: </span>
                  <QuerySyntaxHighlighter query={query} className="text-xs" />
                </div>
              ))}
              {step.data.queries.length > 5 && (
                <p className="text-xs text-muted-foreground/70 italic">
                  ... and {step.data.queries.length - 5} more
                </p>
              )}
            </div>
          )}
        </div>
      );

    case 'ncbi_search':
      return (
        <div className="mt-2 pt-2 border-t border-border space-y-1">
          {step.data.dataset_count !== undefined && (
            <p className="text-xs text-muted-foreground">
              • Found {step.data.dataset_count} unique dataset{step.data.dataset_count === 1 ? '' : 's'}
            </p>
          )}
          {step.total && (
            <p className="text-xs text-muted-foreground">
              • Executed {step.total} search {step.total === 1 ? 'query' : 'queries'}
            </p>
          )}
          {step.data.sample_ids && Array.isArray(step.data.sample_ids) && (
            <div className="space-y-1 ml-2">
              <p className="text-xs text-muted-foreground/70">Sample dataset IDs:</p>
              {step.data.sample_ids.slice(0, 10).map((id: string, idx: number) => (
                <p key={idx} className="text-xs text-muted-foreground/70 font-mono">
                  {id}
                </p>
              ))}
              {step.data.sample_ids.length > 10 && (
                <p className="text-xs text-muted-foreground/70 italic">
                  ... and {step.data.sample_ids.length - 10} more
                </p>
              )}
            </div>
          )}
        </div>
      );

    case 'metadata_fetch':
      return (
        <div className="mt-2 pt-2 border-t border-border space-y-1">
          {step.data.processed_count !== undefined && (
            <p className="text-xs text-muted-foreground">
              • Processed {step.data.processed_count} dataset{step.data.processed_count === 1 ? '' : 's'}
            </p>
          )}
          {step.progress && step.total && (
            <p className="text-xs text-muted-foreground">
              • Progress: {step.progress}/{step.total} ({Math.round((step.progress / step.total) * 100)}%)
            </p>
          )}
        </div>
      );

    case 'filtering':
      return (
        <div className="mt-2 pt-2 border-t border-border space-y-1">
          {step.data.before_count !== undefined && (
            <p className="text-xs text-muted-foreground">
              • Before filtering: {step.data.before_count} datasets
            </p>
          )}
          {step.data.after_count !== undefined && (
            <p className="text-xs text-muted-foreground">
              • After filtering: {step.data.after_count} datasets
            </p>
          )}
          {step.data.criteria && Array.isArray(step.data.criteria) && (
            <div className="space-y-1 ml-2">
              <p className="text-xs text-muted-foreground/70">Filter criteria:</p>
              {step.data.criteria.map((criterion: string, idx: number) => (
                <p key={idx} className="text-xs text-muted-foreground/70">
                  • {criterion}
                </p>
              ))}
            </div>
          )}
        </div>
      );

    case 'results':
      return (
        <div className="mt-2 pt-2 border-t border-border space-y-1">
          {step.data.total_results !== undefined && (
            <p className="text-xs text-muted-foreground">
              • Total results: {step.data.total_results} dataset{step.data.total_results === 1 ? '' : 's'}
            </p>
          )}
          {step.data.elapsed_seconds !== undefined && (
            <p className="text-xs text-muted-foreground">
              • Completed in {step.data.elapsed_seconds.toFixed(1)} seconds
            </p>
          )}
        </div>
      );

    default:
      // Fallback: render raw JSON for unknown step types
      return (
        <div className="mt-2 pt-2 border-t border-border">
          <pre className="text-xs text-muted-foreground font-mono overflow-x-auto">
            {JSON.stringify(step.data, null, 2)}
          </pre>
        </div>
      );
  }
}

export function ReasoningSteps({ steps }: ReasoningStepsProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const allComplete = steps.every(step => step.status === 'complete');
  const isThinking = steps.some(step => step.status === 'running' || step.status === 'pending');

  const toggleStep = (stepId: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  return (
    <div className="space-y-3">
      {isThinking && (
        <div className="flex items-center gap-2">
          <Loader2 className="w-4 h-4 text-signal animate-spin" />
          <p className="text-muted-foreground text-sm">Thinking...</p>
        </div>
      )}

      {allComplete && (
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-positive" />
          <p className="text-positive text-sm">Analysis complete</p>
        </div>
      )}

      <div className="space-y-2">
        {steps.map((step) => {
          const Icon = stepIcons[step.type];
          const hasData = step.data && Object.keys(step.data).length > 0;
          const isExpanded = expandedSteps.has(step.id);

          return (
            <Collapsible.Root
              key={step.id}
              open={isExpanded}
              onOpenChange={() => hasData && toggleStep(step.id)}
            >
              <div
                className={`rounded-lg transition-colors duration-150 ${
                  step.status === 'complete'
                    ? 'bg-surface-1 border border-border'
                    : step.status === 'running'
                    ? 'signal-sweep border border-signal/40'
                    : 'bg-surface-1 border border-border opacity-50'
                }`}
              >
                <Collapsible.Trigger asChild>
                  <div
                    className={`flex items-start gap-3 p-3 ${
                      hasData ? 'cursor-pointer hover:bg-accent' : ''
                    }`}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {step.status === 'complete' && (
                        <CheckCircle2 className="w-5 h-5 text-positive" />
                      )}
                      {step.status === 'running' && (
                        <Loader2 className="w-5 h-5 text-signal animate-spin" />
                      )}
                      {step.status === 'pending' && (
                        <Circle className="w-5 h-5 text-muted-foreground/70" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className={`w-4 h-4 transition-colors ${
                          step.status === 'complete' ? 'text-positive' :
                          step.status === 'running' ? 'text-signal' :
                          'text-muted-foreground/70'
                        }`} />
                        <p className={`text-sm transition-colors ${
                          step.status === 'complete' ? 'text-foreground/90' :
                          step.status === 'running' ? 'text-signal' :
                          'text-muted-foreground'
                        }`}>
                          {step.title}
                        </p>
                      </div>
                      <p className={`text-xs transition-colors ${
                        step.status === 'complete' ? 'text-muted-foreground' :
                        step.status === 'running' ? 'text-signal/80' :
                        'text-muted-foreground/70'
                      }`}>
                        {step.description}
                      </p>
                    </div>

                    {hasData && (
                      <div className="flex-shrink-0 mt-0.5">
                        {isExpanded ? (
                          <ChevronDown className={`w-4 h-4 transition-colors ${
                            step.status === 'complete' ? 'text-positive' :
                            step.status === 'running' ? 'text-signal' :
                            'text-muted-foreground/70'
                          }`} />
                        ) : (
                          <ChevronRight className={`w-4 h-4 transition-colors ${
                            step.status === 'complete' ? 'text-positive' :
                            step.status === 'running' ? 'text-signal' :
                            'text-muted-foreground/70'
                          }`} />
                        )}
                      </div>
                    )}
                  </div>
                </Collapsible.Trigger>

                <Collapsible.Content className="px-3 pb-3">
                  {renderStepDetails(step)}
                </Collapsible.Content>
              </div>
            </Collapsible.Root>
          );
        })}
      </div>
    </div>
  );
}
