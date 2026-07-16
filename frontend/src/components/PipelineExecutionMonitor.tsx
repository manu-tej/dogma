/**
 * Pipeline Execution Monitor Component
 *
 * Monitor and display the status of pipeline executions.
 */

import { useState, useEffect } from "react";
import {
  pipelineClient,
  type PipelineExecution,
  type PipelineStatus,
} from "../lib/pipeline-client";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { ScrollArea } from "./ui/scroll-area";

interface PipelineExecutionMonitorProps {
  executionId?: string; // If provided, monitor specific execution
  autoRefresh?: boolean; // Auto-refresh enabled
  refreshInterval?: number; // Refresh interval in milliseconds
}

export function PipelineExecutionMonitor({
  executionId,
  autoRefresh = true,
  refreshInterval = 5000,
}: PipelineExecutionMonitorProps) {
  const [executions, setExecutions] = useState<PipelineExecution[]>([]);
  const [selectedExecution, setSelectedExecution] =
    useState<PipelineExecution | null>(null);
  const [logs, setLogs] = useState<string | null>(null);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadExecutions();

    if (autoRefresh) {
      const interval = setInterval(loadExecutions, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [executionId, autoRefresh, refreshInterval]);

  const loadExecutions = async () => {
    try {
      setError(null);

      if (executionId) {
        // Load specific execution
        const { execution } = await pipelineClient.getExecutionStatus(executionId);
        setExecutions([execution]);
      } else {
        // Load all executions
        const allExecutions = await pipelineClient.listExecutions();
        setExecutions(allExecutions);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load executions");
    } finally {
      setLoading(false);
    }
  };

  const handleViewLogs = async (execution: PipelineExecution) => {
    try {
      const { logs: executionLogs } = await pipelineClient.getExecutionStatus(
        execution.execution_id,
        { includeLogs: true, logLines: 500 }
      );
      setLogs(executionLogs || "No logs available");
      setSelectedExecution(execution);
      setShowLogsDialog(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load logs");
    }
  };

  const handleCancelExecution = async (execution: PipelineExecution) => {
    if (!confirm(`Cancel execution ${execution.execution_id}?`)) {
      return;
    }

    try {
      await pipelineClient.cancelExecution(execution.execution_id);
      await loadExecutions(); // Refresh list
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel execution");
    }
  };

  const getStatusBadge = (status: PipelineStatus) => {
    const variants: Record<
      PipelineStatus,
      "default" | "secondary" | "destructive" | "outline"
    > = {
      pending: "outline",
      queued: "secondary",
      running: "default",
      completed: "default",
      failed: "destructive",
      cancelled: "secondary",
    };

    return (
      <Badge variant={variants[status]} className="capitalize">
        {status}
      </Badge>
    );
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return "—";

    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const durationMs = endTime - startTime;

    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((durationMs % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  if (loading && executions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="signal-sweep text-muted-foreground rounded-lg px-4 py-2">Loading executions...</p>
      </div>
    );
  }

  if (error && executions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-destructive mb-2">Error loading executions</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button onClick={loadExecutions} className="mt-4">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Pipeline Executions</h2>
          <p className="text-muted-foreground">
            Monitor running and completed pipeline executions
          </p>
        </div>
        <Button onClick={loadExecutions} variant="outline">
          Refresh
        </Button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {/* Executions Table */}
      <Card className="bg-card border-border elev">
        <CardHeader>
          <CardTitle className="text-foreground">Recent Executions</CardTitle>
          <CardDescription className="text-muted-foreground">
            <span className="font-mono">{executions.length}</span> execution{executions.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Pipeline</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {executions.map((execution) => (
                <TableRow
                  key={execution.execution_id}
                  className={execution.status === "running" ? "signal-sweep" : undefined}
                >
                  <TableCell>
                    <div>
                      <p className="font-medium text-foreground">{execution.pipeline_id}</p>
                      <p className="text-xs text-muted-foreground font-mono">
                        {execution.execution_id.slice(0, 8)}...
                      </p>
                    </div>
                  </TableCell>
                  <TableCell>{getStatusBadge(execution.status)}</TableCell>
                  <TableCell>
                    <div className="w-32">
                      <Progress value={execution.progress_percent} />
                      <p className="text-xs text-muted-foreground mt-1 font-mono">
                        {execution.progress_percent.toFixed(0)}%
                      </p>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm font-mono text-muted-foreground">
                    {formatDuration(execution.started_at, execution.completed_at)}
                  </TableCell>
                  <TableCell className="text-sm font-mono text-muted-foreground">
                    {execution.started_at
                      ? new Date(execution.started_at).toLocaleString()
                      : "Not started"}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleViewLogs(execution)}
                      >
                        Logs
                      </Button>
                      {execution.status === "running" && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleCancelExecution(execution)}
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {executions.length === 0 && (
            <div className="text-center py-12">
              <p className="text-muted-foreground/70">No executions found</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Logs Dialog */}
      <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh] elev">
          <DialogHeader>
            <DialogTitle className="text-foreground">
              Execution Logs
              {selectedExecution && ` - ${selectedExecution.pipeline_id}`}
            </DialogTitle>
            <DialogDescription className="font-mono text-muted-foreground">
              {selectedExecution?.execution_id}
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="h-[60vh]">
            <pre className="font-mono text-xs bg-surface-2 text-foreground/90 p-4 rounded-lg overflow-x-auto">
              {logs || "Loading logs..."}
            </pre>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
