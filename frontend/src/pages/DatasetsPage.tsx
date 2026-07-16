import { useState, type ReactNode } from "react";
import { Search } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { useGeoSearch } from "../hooks/useGeoSearch";
import {
  searchSingleCell,
  searchProteomics,
  type SingleCellDataset,
  type ProteomicsDataset,
} from "../services/datasetsService";

/** Shared search-box + result-list scaffold so every repository tab feels the same. */
function SearchPanel<T>({
  placeholder,
  emptyHint,
  onSearch,
  renderResult,
  resultKey,
}: {
  placeholder: string;
  emptyHint: string;
  onSearch: (query: string) => Promise<T[]>;
  renderResult: (item: T) => ReactNode;
  resultKey: (item: T) => string;
}) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<T[] | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResults(await onSearch(query.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex gap-2">
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={placeholder} className="flex-1" />
        <Button type="submit" disabled={loading || !query.trim()}>
          <Search className="mr-1.5 h-4 w-4" />
          {loading ? "Searching…" : "Search"}
        </Button>
      </form>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="signal-sweep h-16 w-full rounded-lg border border-border bg-card" />
          ))}
        </div>
      )}
      {results && results.length === 0 && !loading && (
        <p className="text-sm text-muted-foreground">No datasets matched that query.</p>
      )}
      {results && results.length > 0 && (
        <ul className="stagger space-y-2">
          {results.map((item, i) => (
            <li
              key={resultKey(item)}
              className="elev animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card p-3 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
              style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
            >
              {renderResult(item)}
            </li>
          ))}
        </ul>
      )}
      {!results && !loading && <p className="text-sm text-muted-foreground/70">{emptyHint}</p>}
    </div>
  );
}

function GeoSearchPanel() {
  const { search, loading, error, results } = useGeoSearch();
  const [query, setQuery] = useState("");
  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) void search(query.trim());
        }}
        className="flex gap-2"
      >
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. breast cancer RNA-seq tamoxifen resistance"
          className="flex-1"
        />
        <Button type="submit" disabled={loading || !query.trim()}>
          <Search className="mr-1.5 h-4 w-4" />
          {loading ? "Searching…" : "Search"}
        </Button>
      </form>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="signal-sweep h-16 w-full rounded-lg border border-border bg-card" />
          ))}
        </div>
      )}
      {results && results.length === 0 && !loading && (
        <p className="text-sm text-muted-foreground">No datasets matched that query.</p>
      )}
      {results && results.length > 0 && (
        <ul className="stagger space-y-2">
          {results.map((r, i) => (
            <li
              key={r.gseId}
              className="elev animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card p-3 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
              style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
            >
              <Accession id={r.gseId} title={r.title} />
              <div className="mt-1 text-xs text-muted-foreground">{r.organism} · {r.nSamples} samples</div>
              {r.summary && <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground/70">{r.summary}</p>}
            </li>
          ))}
        </ul>
      )}
      {!results && !loading && (
        <div className="space-y-3 pt-1">
          <p className="text-sm text-muted-foreground/70">
            Search the Gene Expression Omnibus by natural-language query, or try one:
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              "breast cancer RNA-seq tamoxifen resistance",
              "melanoma single-cell immunotherapy",
              "Alzheimer hippocampus transcriptomics",
            ].map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setQuery(ex);
                  void search(ex);
                }}
                className="rounded-full border border-border bg-surface-1 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground active:scale-[0.98]"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Accession({ id, title }: { id: string; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="elev-sm rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-signal">{id}</span>
      <span className="text-sm font-medium text-foreground">{title}</span>
    </div>
  );
}

/** Dataset discovery across GEO, single-cell, and proteomics (PRIDE). */
export function DatasetsPage() {
  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Datasets" description="Search GEO, single-cell, and proteomics (PRIDE) repositories." />
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <Tabs defaultValue="geo" className="w-full">
          <TabsList>
            <TabsTrigger value="geo">GEO</TabsTrigger>
            <TabsTrigger value="single-cell">Single-cell</TabsTrigger>
            <TabsTrigger value="proteomics">Proteomics</TabsTrigger>
          </TabsList>

          <TabsContent value="geo" className="mt-4">
            <GeoSearchPanel />
          </TabsContent>

          <TabsContent value="single-cell" className="mt-4">
            <SearchPanel<SingleCellDataset>
              placeholder="e.g. immune cells tumor microenvironment"
              emptyHint="Search GEO for single-cell RNA-seq datasets with downloadable matrices."
              onSearch={(q) => searchSingleCell(q)}
              resultKey={(d) => d.accession}
              renderResult={(d) => (
                <>
                  <Accession id={d.accession} title={d.title} />
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>{d.organism}</span>
                    {d.n_samples != null && <span>· {d.n_samples} samples</span>}
                    {d.has_h5ad && <Badge variant="secondary" className="text-[10px]">.h5ad</Badge>}
                    {d.has_mtx && <Badge variant="secondary" className="text-[10px]">.mtx</Badge>}
                  </div>
                  {d.summary && <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground/70">{d.summary}</p>}
                </>
              )}
            />
          </TabsContent>

          <TabsContent value="proteomics" className="mt-4">
            <SearchPanel<ProteomicsDataset>
              placeholder="e.g. breast cancer phosphoproteomics"
              emptyHint="Search the PRIDE Archive for mass-spec proteomics datasets."
              onSearch={(q) => searchProteomics(q)}
              resultKey={(d) => d.accession}
              renderResult={(d) => (
                <>
                  <Accession id={d.accession} title={d.title} />
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {d.organism && <span>{d.organism}</span>}
                    {d.nAssays != null && <span>· {d.nAssays} assays</span>}
                    {d.hasQuantificationData && <Badge variant="secondary" className="text-[10px]">quantified</Badge>}
                    {d.instruments.slice(0, 2).map((inst) => (
                      <Badge key={inst} variant="outline" className="text-[10px]">{inst}</Badge>
                    ))}
                  </div>
                  {d.description && <p className="mt-1.5 line-clamp-2 text-xs text-muted-foreground/70">{d.description}</p>}
                </>
              )}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
