/**
 * Method Browser Component
 *
 * Allows users to browse available analysis methods and get recommendations
 */

import { useState, useEffect } from "react";
import { Search, Filter, Star, GitBranch, FileCode, AlertCircle } from "lucide-react";
import {
  listMethods,
  matchMethods,
  getStats,
  type AnalysisMethod,
  type MethodResponse,
  type RegistryStats,
} from "../services/brokerService";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Alert, AlertDescription } from "./ui/alert";

export function MethodBrowser() {
  const [methods, setMethods] = useState<AnalysisMethod[]>([]);
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [nlQuery, setNlQuery] = useState("");
  const [recommendations, setRecommendations] = useState<MethodResponse | null>(null);

  useEffect(() => {
    loadMethods();
    loadStats();
  }, []);

  const loadMethods = async () => {
    try {
      setLoading(true);
      const data = await listMethods();
      setMethods(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load methods");
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  const handleSearch = async () => {
    try {
      setLoading(true);
      const data = await listMethods({ search: searchQuery });
      setMethods(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGetRecommendations = async () => {
    if (!nlQuery.trim()) return;

    try {
      setLoading(true);
      setError(null);
      const response = await matchMethods({
        query: nlQuery,
        max_recommendations: 5,
        prefer_published: true,
        prefer_reproducible: true,
      });
      setRecommendations(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get recommendations");
    } finally {
      setLoading(false);
    }
  };

  const MethodCard = ({ method }: { method: AnalysisMethod }) => (
    <Card className="mb-4 bg-card border-border elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-lg text-foreground">{method.name}</CardTitle>
            <CardDescription className="mt-1 text-muted-foreground">
              {method.category.replace(/_/g, " ")} · <span className="font-mono">v{method.version}</span>
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {method.quality_metrics.peer_reviewed && (
              <Badge variant="secondary">
                <Star className="w-3 h-3 mr-1" />
                Peer Reviewed
              </Badge>
            )}
            {method.quality_metrics.code_availability && (
              <Badge variant="outline">
                <FileCode className="w-3 h-3 mr-1" />
                Open Source
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-3">{method.description}</p>

        <div className="grid grid-cols-2 gap-4 mb-3">
          <div>
            <p className="text-xs font-semibold mb-1 text-foreground">Implementation</p>
            <Badge variant="outline">{method.implementation_type}</Badge>
          </div>
          <div>
            <p className="text-xs font-semibold mb-1 text-foreground">Modalities</p>
            <div className="flex flex-wrap gap-1">
              {method.supported_modalities.map((mod) => (
                <Badge key={mod} variant="secondary" className="text-xs">
                  {mod.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          </div>
        </div>

        {/* Labelled as estimates, and deliberately not in monospace.
            These are hand-entered curator judgements: reproducibility, rating and
            documentation have no rubric or rater pool behind them, and the
            citation count was typed once and never refreshed. Rendering them as
            `95%` / `15,000` / `4.8/5.0` in monospace read as measurement, which is
            what the styling convention means. See MethodQualityMetrics. */}
        <div className="mb-3 text-xs text-muted-foreground">
          <div className="mb-1 italic">
            {method.quality_metrics.provenance === "measured"
              ? "Measured:"
              : "Curator estimates — not measured:"}
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <span className="font-semibold text-foreground">Reproducibility:</span>{" "}
              <span>~{(method.quality_metrics.reproducibility_score * 100).toFixed(0)}%</span>
            </div>
            <div>
              <span className="font-semibold text-foreground">Citations:</span>{" "}
              <span>~{method.quality_metrics.citation_count.toLocaleString()}</span>
            </div>
            {method.quality_metrics.community_rating && (
              <div>
                <span className="font-semibold text-foreground">Rating:</span>{" "}
                <span>~{method.quality_metrics.community_rating.toFixed(1)}/5.0</span>
              </div>
            )}
          </div>
        </div>

        {method.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {method.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {(method.repository_url || method.documentation_url) && (
          <div className="flex gap-2 mt-3">
            {method.repository_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={method.repository_url} target="_blank" rel="noopener noreferrer">
                  <GitBranch className="w-3 h-3 mr-1" />
                  Repository
                </a>
              </Button>
            )}
            {method.documentation_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={method.documentation_url} target="_blank" rel="noopener noreferrer">
                  Documentation
                </a>
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );

  const RecommendationCard = ({ match, rank }: { match: any; rank: number }) => (
    <Card className={`mb-4 bg-card elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong ${match.recommended ? "border-signal/50" : "border-border"}`}>
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant={rank === 1 ? "default" : "secondary"} className="font-mono">
                #{rank}
              </Badge>
              <CardTitle className="text-lg text-foreground">{match.method.name}</CardTitle>
            </div>
            <CardDescription className="mt-1 text-muted-foreground">
              Match Score: <span className="font-mono">{(match.score * 100).toFixed(0)}%</span>
              {match.recommended && " · Recommended"}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-3">{match.method.description}</p>

        {match.match_reasons.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-semibold mb-1 text-foreground">Why this matches:</p>
            <ul className="text-sm space-y-1 text-foreground/90">
              {match.match_reasons.map((reason: string, i: number) => (
                <li key={i} className="flex items-start">
                  <span className="mr-2 text-signal">✓</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {match.potential_issues.length > 0 && (
          <Alert className="mb-3 elev">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <p className="font-semibold mb-1 text-foreground">Considerations:</p>
              <ul className="text-sm space-y-1">
                {match.potential_issues.map((issue: string, i: number) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div>
            <span className="font-semibold text-foreground">Relevance:</span>{" "}
            <span className="font-mono">{(match.relevance_score * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span className="font-semibold text-foreground">Quality:</span>{" "}
            <span className="font-mono">{(match.quality_score * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span className="font-semibold text-foreground">Compatibility:</span>{" "}
            <span className="font-mono">{(match.compatibility_score * 100).toFixed(0)}%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2 text-foreground">Method Broker</h1>
        <p className="text-muted-foreground">
          Discover and match analysis methods to your research needs
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <Card className="bg-card border-border elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Methods</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono text-foreground">{stats.registry.total_methods}</div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong">
            <CardHeader className="pb-3">
              {/* An average of curator estimates is still an estimate. The tile
                  said "Avg Quality" over a monospace percentage, which presented
                  the mean of some hand-typed numbers as a measured property of the
                  registry. */}
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Avg Quality (estimated)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">
                ~{(stats.registry.average_quality_score * 100).toFixed(0)}%
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">Proposals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono text-foreground">{stats.proposals.total_proposals}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="browse" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="browse">Browse Methods</TabsTrigger>
          <TabsTrigger value="recommend">Get Recommendations</TabsTrigger>
        </TabsList>

        <TabsContent value="browse" className="space-y-4">
          <div className="flex gap-2">
            <div className="flex-1">
              <Input
                placeholder="Search methods by keyword..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button onClick={handleSearch} disabled={loading}>
              <Search className="w-4 h-4 mr-2" />
              Search
            </Button>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="signal-sweep text-center py-8 text-muted-foreground rounded-lg">Loading methods...</div>
          ) : (
            <div>
              {methods.map((method) => (
                <MethodCard key={method.id} method={method} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="recommend" className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block text-foreground">
              Describe your analysis needs:
            </label>
            <Input
              placeholder="e.g., I need to call variants from whole genome sequencing data"
              value={nlQuery}
              onChange={(e) => setNlQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGetRecommendations()}
            />
            <Button onClick={handleGetRecommendations} disabled={loading} className="mt-2">
              Get Recommendations
            </Button>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {recommendations && (
            <div>
              <Card className="mb-4 bg-card border-border elev">
                <CardHeader>
                  <CardTitle className="text-foreground">Parsed Request</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
                    <div>
                      <span className="font-semibold text-foreground">Data Modality:</span>{" "}
                      {recommendations.parsed_request.data_modality.replace(/_/g, " ")}
                    </div>
                    <div>
                      <span className="font-semibold text-foreground">Analysis Type:</span>{" "}
                      {recommendations.parsed_request.analysis_type}
                    </div>
                    {recommendations.parsed_request.organism && (
                      <div>
                        <span className="font-semibold text-foreground">Organism:</span>{" "}
                        {recommendations.parsed_request.organism}
                      </div>
                    )}
                    <div>
                      <span className="font-semibold text-foreground">Confidence:</span>{" "}
                      <span className="font-mono">{(recommendations.parsed_request.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <h3 className="text-xl font-semibold mb-3 text-foreground">Recommended Methods</h3>
              {recommendations.matches.map((match) => (
                <RecommendationCard key={match.method.id} match={match} rank={match.rank} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
