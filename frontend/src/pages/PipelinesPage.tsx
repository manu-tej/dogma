import { useState } from "react";

import { PipelineBrowser } from "../components/PipelineBrowser";
import { PipelineExecutionMonitor } from "../components/PipelineExecutionMonitor";
import { PipelineLaunchDialog } from "../components/PipelineLaunchDialog";
import { PageHeader } from "../components/PageHeader";
import type { PipelineCatalogEntry } from "../lib/pipeline-client";

/**
 * Nextflow pipeline catalog + launch + execution monitor. Selecting a pipeline
 * opens the launch dialog; a successful launch bumps the monitor to refetch.
 */
export function PipelinesPage() {
  const [selected, setSelected] = useState<PipelineCatalogEntry | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [monitorKey, setMonitorKey] = useState(0);

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Pipelines" description="Browse, launch, and monitor Nextflow pipeline runs." />
      <div className="min-h-0 flex-1 space-y-8 overflow-y-auto p-6">
        <PipelineBrowser
          onSelectPipeline={(p) => {
            setSelected(p);
            setDialogOpen(true);
          }}
        />
        <section>
          <h2 className="mb-3 text-sm font-semibold text-foreground">Recent executions</h2>
          <PipelineExecutionMonitor key={monitorKey} autoRefresh />
        </section>
      </div>

      <PipelineLaunchDialog
        pipeline={selected}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onLaunched={() => setMonitorKey((k) => k + 1)}
      />
    </div>
  );
}
