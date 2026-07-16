import { useEffect, useState } from "react";
import { Rocket, Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  pipelineClient,
  type PipelineCatalogEntry,
  type PipelineParameter,
} from "../lib/pipeline-client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Switch } from "./ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const PROFILES = ["test", "docker", "singularity", "conda"];

interface PipelineLaunchDialogProps {
  pipeline: PipelineCatalogEntry | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the new execution id after a successful launch. */
  onLaunched: (executionId: string) => void;
}

/** Initial parameter values from a pipeline's required parameters' defaults. */
function initialParams(pipeline: PipelineCatalogEntry | null): Record<string, any> {
  const out: Record<string, any> = {};
  for (const p of pipeline?.parameters ?? []) {
    if (p.required && p.name !== "input" && p.name !== "outdir") {
      out[p.name] = p.default ?? (p.type === "boolean" ? false : "");
    }
  }
  return out;
}

/** Render the right control for a parameter's type. */
function ParamField({
  param,
  value,
  onChange,
}: {
  param: PipelineParameter;
  value: any;
  onChange: (v: any) => void;
}) {
  if (param.type === "boolean") {
    return <Switch checked={Boolean(value)} onCheckedChange={onChange} />;
  }
  if (param.type === "choice" && param.choices?.length) {
    return (
      <Select value={String(value ?? "")} onValueChange={onChange}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select…" />
        </SelectTrigger>
        <SelectContent>
          {param.choices.map((c) => (
            <SelectItem key={c} value={c}>{c}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  const numeric = param.type === "integer" || param.type === "float";
  return (
    <Input
      type={numeric ? "number" : "text"}
      value={value ?? ""}
      placeholder={param.example ?? param.description}
      onChange={(e) => onChange(numeric ? Number(e.target.value) : e.target.value)}
    />
  );
}

/** A dialog to configure and launch a Nextflow pipeline run. */
export function PipelineLaunchDialog({ pipeline, open, onOpenChange, onLaunched }: PipelineLaunchDialogProps) {
  const [samplesheet, setSamplesheet] = useState("");
  const [profile, setProfile] = useState("test");
  const [params, setParams] = useState<Record<string, any>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset the form whenever a new pipeline is opened.
  useEffect(() => {
    if (open) {
      setParams(initialParams(pipeline));
      setSamplesheet("");
      setProfile("test");
      setError(null);
    }
  }, [open, pipeline]);

  const requiredParams = (pipeline?.parameters ?? []).filter(
    (p) => p.required && p.name !== "input" && p.name !== "outdir",
  );

  const launch = async () => {
    if (!pipeline) return;
    if (!samplesheet.trim()) {
      setError("A samplesheet path or URL is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await pipelineClient.executePipeline({
        pipeline_id: pipeline.id,
        pipeline_version: pipeline.version,
        input_spec: { input_files: [], samplesheet: samplesheet.trim() },
        parameters: params,
        profile,
        resume: false,
      });
      toast.success(`Launched ${pipeline.name} — ${res.execution_id}`);
      onLaunched(res.execution_id);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto elev">
        <DialogHeader>
          <DialogTitle className="text-foreground">Launch {pipeline?.name ?? "pipeline"}</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {pipeline?.version && <span className="mr-2 font-mono text-xs text-signal">{pipeline.version}</span>}
            Configure inputs and run on Nextflow.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">Samplesheet (path or URL)</span>
            <Input
              value={samplesheet}
              onChange={(e) => setSamplesheet(e.target.value)}
              placeholder="s3://… or /data/samplesheet.csv"
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">Profile</span>
            <Select value={profile} onValueChange={setProfile}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROFILES.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>

          {requiredParams.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground/70">
                Required parameters
              </p>
              {requiredParams.map((p) => (
                <label key={p.name} className="block text-sm">
                  <span className="mb-1 flex items-center justify-between text-muted-foreground">
                    <span className="font-mono text-xs text-foreground/90">{p.name}</span>
                  </span>
                  <ParamField
                    param={p}
                    value={params[p.name]}
                    onChange={(v) => setParams((prev) => ({ ...prev, [p.name]: v }))}
                  />
                  {p.description && <span className="mt-1 block text-xs text-muted-foreground/70">{p.description}</span>}
                </label>
              ))}
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={launch} disabled={submitting || !pipeline} className="glow-signal">
            {submitting ? (
              <>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Launching…
              </>
            ) : (
              <>
                <Rocket className="mr-1.5 h-4 w-4" /> Launch run
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
