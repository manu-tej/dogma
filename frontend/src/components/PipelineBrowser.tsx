/**
 * Pipeline Browser Component
 *
 * Browse and filter available Nextflow pipelines.
 */

import { useState, useEffect } from "react";
import {
  pipelineClient,
  type PipelineCatalogEntry,
  type OmicsType,
} from "../lib/pipeline-client";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

interface PipelineBrowserProps {
  onSelectPipeline?: (pipeline: PipelineCatalogEntry) => void;
}

export function PipelineBrowser({ onSelectPipeline }: PipelineBrowserProps) {
  const [pipelines, setPipelines] = useState<PipelineCatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [omicsFilter, setOmicsFilter] = useState<OmicsType | "all">("all");

  useEffect(() => {
    loadPipelines();
  }, [omicsFilter]);

  const loadPipelines = async () => {
    try {
      setLoading(true);
      setError(null);

      const results = await pipelineClient.listPipelines({
        omicsType: omicsFilter === "all" ? undefined : omicsFilter,
        search: searchQuery || undefined,
      });

      setPipelines(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pipelines");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    loadPipelines();
  };

  const filteredPipelines = pipelines.filter((pipeline) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        pipeline.name.toLowerCase().includes(query) ||
        pipeline.description.toLowerCase().includes(query) ||
        pipeline.tags.some((tag) => tag.toLowerCase().includes(query))
      );
    }
    return true;
  });

  if (loading && pipelines.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="signal-sweep text-muted-foreground rounded-lg px-4 py-2">Loading pipelines...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-destructive mb-2">Error loading pipelines</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button onClick={loadPipelines} className="mt-4">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 text-foreground">Nextflow Pipelines</h2>
        <p className="text-muted-foreground">
          Browse and execute nf-core bioinformatics pipelines
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search pipelines..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Select
          value={omicsFilter}
          onValueChange={(value) => setOmicsFilter(value as OmicsType | "all")}
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="bulk_rnaseq">Bulk RNA-seq</SelectItem>
            <SelectItem value="single_cell">Single-cell</SelectItem>
            <SelectItem value="proteomics">Proteomics</SelectItem>
            <SelectItem value="metabolomics">Metabolomics</SelectItem>
            <SelectItem value="genomics">Genomics</SelectItem>
            <SelectItem value="epigenomics">Epigenomics</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={handleSearch}>Search</Button>
      </div>

      {/* Pipeline Cards */}
      <div className="stagger grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPipelines.map((pipeline, i) => (
          <Card
            key={pipeline.id}
            className="flex flex-col bg-card border-border elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong animate-in fade-in slide-in-from-bottom-2"
            style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <CardTitle className="text-lg text-foreground">{pipeline.name}</CardTitle>
                  <CardDescription className="text-xs mt-1 font-mono text-muted-foreground">
                    {pipeline.id} v{pipeline.version}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1">
              <p className="text-sm text-muted-foreground mb-3">
                {pipeline.description}
              </p>

              {/* Omics Types */}
              <div className="flex flex-wrap gap-1 mb-3">
                {pipeline.omics_types.map((type) => (
                  <Badge key={type} variant="secondary" className="text-xs">
                    {type.replace("_", "-")}
                  </Badge>
                ))}
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-1">
                {pipeline.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
                {pipeline.tags.length > 3 && (
                  <Badge variant="outline" className="text-xs">
                    +{pipeline.tags.length - 3}
                  </Badge>
                )}
              </div>

              {/* Resource Info */}
              {pipeline.recommended_cpus && (
                <div className="mt-3 text-xs text-muted-foreground">
                  <p>Recommended: <span className="font-mono">{pipeline.recommended_cpus}</span> CPUs</p>
                  {pipeline.recommended_memory_gb && (
                    <p><span className="font-mono">{pipeline.recommended_memory_gb}</span> GB RAM</p>
                  )}
                  {pipeline.estimated_runtime_hours && (
                    <p>~<span className="font-mono">{pipeline.estimated_runtime_hours}h</span> runtime</p>
                  )}
                </div>
              )}
            </CardContent>
            <CardFooter className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                asChild
                className="flex-1"
              >
                <a
                  href={pipeline.documentation_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Docs
                </a>
              </Button>
              {onSelectPipeline && (
                <Button
                  size="sm"
                  onClick={() => onSelectPipeline(pipeline)}
                  className="flex-1"
                >
                  Configure
                </Button>
              )}
            </CardFooter>
          </Card>
        ))}
      </div>

      {filteredPipelines.length === 0 && !loading && (
        <div className="text-center py-12">
          <p className="text-muted-foreground/70">
            No pipelines found matching your criteria
          </p>
        </div>
      )}
    </div>
  );
}
