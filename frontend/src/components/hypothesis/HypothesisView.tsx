import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Panel, type ImperativePanelHandle } from "react-resizable-panels";
import { PanelLeftOpen, RotateCw } from "lucide-react";

import type { EvidenceEntry, ProposedTest } from "../../lib/hypothesis-client";
import { useHypothesis } from "../../hooks/useHypothesis";
import { Button } from "../ui/button";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "../ui/resizable";
import { cn } from "../ui/utils";
import { ActivityPanel } from "./ActivityPanel";
import { CausalCanvas } from "./CausalCanvas";
import { EdgePanels } from "./EdgePanels";
import { HistorySidebar } from "./HistorySidebar";
import { NodePanel } from "./NodePanel";
import { GroundedAnswerCard } from "./GroundedAnswerCard";
import { QueryBar } from "./QueryBar";
import { LoadingSpinner } from "../LoadingSpinner";

interface HypothesisViewProps {
  /** Question carried over from the chat; prefilled + auto-investigated on open. */
  initialQuery?: string;
  /** A saved graph id to load on open (deep-link from /canvas/:graphId). */
  initialGraphId?: string;
  /** Controls rendered at the right of the top bar (e.g. the Canvas/Chat toggle). */
  headerRight?: ReactNode;
}

const HISTORY_COLLAPSED_KEY = "anton:historyCollapsed";

/** Trim the investigation question to a breadcrumb-sized crumb. */
function crumb(q: string, max = 52): string {
  const t = q.trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

export function HypothesisView({ initialQuery, initialGraphId, headerRight }: HypothesisViewProps) {
  const { state, runQuery, selectEdge, selectNode, approve, skip, loadGraph, reset } = useHypothesis();
  // Evidence entries observed this session, keyed by edge id.
  const [evidence, setEvidence] = useState<Record<string, EvidenceEntry[]>>({});
  const [activityOpen, setActivityOpen] = useState(false);

  // "New canvas" clears the hook (graph/proposal/query) back to the idle hero.
  const handleNewCanvas = () => reset();

  // A question carried over from the chat auto-investigates once, on open. The ref
  // guards against re-firing on later renders or after "New canvas".
  const didAutoStart = useRef(false);
  useEffect(() => {
    if (!didAutoStart.current && initialQuery?.trim() && !state.graph && state.status === "idle") {
      didAutoStart.current = true;
      runQuery(initialQuery);
    }
  }, [initialQuery, state.graph, state.status, runQuery]);

  // A graph id from a /canvas/:graphId deep-link loads that saved graph once.
  const didAutoLoad = useRef(false);
  useEffect(() => {
    if (!didAutoLoad.current && initialGraphId && !state.graph && state.status === "idle") {
      didAutoLoad.current = true;
      loadGraph(initialGraphId);
    }
  }, [initialGraphId, state.graph, state.status, loadGraph]);

  // History sidebar: a collapsible resizable panel. We drive collapse imperatively
  // (button + ⌘B + drag) and animate it via a flex transition that's disabled while
  // dragging so the handle stays glued to the cursor.
  const historyRef = useRef<ImperativePanelHandle>(null);
  const [historyCollapsed, setHistoryCollapsed] = useState(
    () => localStorage.getItem(HISTORY_COLLAPSED_KEY) === "true",
  );
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    localStorage.setItem(HISTORY_COLLAPSED_KEY, String(historyCollapsed));
  }, [historyCollapsed]);

  // ⌘B / Ctrl+B toggles the sidebar (matches the common editor shortcut).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "b" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        const panel = historyRef.current;
        if (!panel) return;
        panel.isCollapsed() ? panel.expand() : panel.collapse();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selectedEdge = useMemo(
    () => state.graph?.edges.find((e) => e.id === state.selectedEdgeId) ?? null,
    [state.graph, state.selectedEdgeId],
  );
  const selectedNode = useMemo(
    () => state.graph?.nodes.find((n) => n.id === state.selectedNodeId) ?? null,
    [state.graph, state.selectedNodeId],
  );
  const nodeLabel = (id: string) =>
    state.graph?.nodes.find((n) => n.id === id)?.label ?? id;

  const handleApprove = async (proposed: ProposedTest) => {
    const entry = await approve(proposed);
    if (!entry) return; // run failed (toasted in the hook); don't record a phantom entry.
    // Record the REAL evidence entry the backend returned — carries the actual
    // direction/magnitude/provenance (correlation verdict, or methods-graph
    // grounding with data_accession="methods-graph"). Surfaces in the ledger +
    // the MethodGroundingPanel.
    setEvidence((prev) => ({
      ...prev,
      [proposed.edge_id]: [...(prev[proposed.edge_id] ?? []), entry],
    }));
  };

  const loading = state.status === "loading";
  const isSimple = state.startKind === "simple" && !state.graph;

  // A slim breadcrumb bar — brand, investigation, the selected edge, the
  // "agent planned · you steer" cue, Re-plan, and the Canvas/Chat toggle. Always
  // present (hero, loading, and canvas) so the toggle stays reachable.
  const topBar = (
    <div className="shrink-0 border-b border-border bg-card px-4 py-2">
      <div className="flex items-center gap-3">
        <div className="flex min-w-0 items-center gap-2 text-xs">
          <span className="font-semibold text-foreground">
            <span className="text-signal">d</span>ogma
          </span>
          {state.query && (
            <>
              <span className="text-muted-foreground/70">›</span>
              <span className="truncate text-muted-foreground" title={state.query}>
                {crumb(state.query)}
              </span>
            </>
          )}
          {selectedEdge && !state.selectedNodeId && (
            <>
              <span className="text-muted-foreground/70">›</span>
              <span className="whitespace-nowrap font-mono text-foreground/90">
                edge: {nodeLabel(selectedEdge.source_id)} → {nodeLabel(selectedEdge.target_id)}
              </span>
            </>
          )}
        </div>
        <div className="flex-1" />
        {selectedEdge && !state.selectedNodeId && (
          <span className="flex items-center gap-1.5 truncate whitespace-nowrap rounded-full border border-signal/40 bg-surface-2 px-3 py-1 text-[11px] text-muted-foreground">
            <span className="text-signal">✦</span> Agent planned this evaluation · you steer
          </span>
        )}
        {state.graph && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setActivityOpen((o) => !o)}
            aria-expanded={activityOpen}
          >
            Activity
          </Button>
        )}
        {state.graph && state.query && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => runQuery(state.query)}
            disabled={loading}
            className="gap-1.5"
          >
            <RotateCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Re-plan
          </Button>
        )}
        {headerRight}
      </div>
      {state.graph && activityOpen && (
        <div className="elev mt-2 max-h-64 overflow-auto rounded-md border border-border bg-background">
          <ActivityPanel graphId={state.graph.id} />
        </div>
      )}
    </div>
  );

  // The body under the bar: an authoring hero / loading spinner when there's no
  // graph yet, a grounded answer for a "simple" start, otherwise the canvas split.
  const body =
    !state.graph && !isSimple ? (
      loading ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-4">
          <LoadingSpinner size="lg" variant="primary" text="Authoring your hypothesis…" />
          {state.query && (
            <p className="max-w-md text-center text-sm text-muted-foreground">{state.query}</p>
          )}
        </div>
      ) : (
        <div className="flex h-full flex-col items-center justify-center px-4 pb-[10vh]">
          <div className="w-full max-w-2xl text-center animate-in fade-in slide-in-from-bottom-2">
            <h2 className="mb-2 text-2xl font-semibold text-foreground">What do you want to investigate?</h2>
            <p className="mb-6 text-sm text-muted-foreground">
              Pose a causal question — I'll author a full causal mechanism you can test and re-roll.
            </p>
            <QueryBar loading={loading} onSubmit={runQuery} initialValue={initialQuery} size="lg" />
            <p className="mt-3 text-xs text-muted-foreground/70">↳ builds an interactive causal canvas</p>
          </div>
        </div>
      )
    ) : isSimple ? (
      <GroundedAnswerCard query={state.query} onEscalate={() => runQuery(state.query)} />
    ) : (
      <ResizablePanelGroup direction="horizontal" className="h-full">
        <ResizablePanel defaultSize={65} minSize={40}>
          <CausalCanvas
            graph={state.graph!}
            graphId={state.graph!.id}
            selectedEdgeId={state.selectedEdgeId}
            selectedNodeId={state.selectedNodeId}
            onSelectEdge={selectEdge}
            onSelectNode={selectNode}
            onGraphChanged={() => loadGraph(state.graph!.id)}
            title={state.query}
          />
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={35} minSize={25}>
          {state.selectedNodeId ? (
            <NodePanel
              node={selectedNode}
              graphId={state.graph!.id}
              onGraphChanged={() => loadGraph(state.graph!.id)}
            />
          ) : (
            <EdgePanels
              edge={selectedEdge}
              sourceLabel={selectedEdge ? nodeLabel(selectedEdge.source_id) : ""}
              targetLabel={selectedEdge ? nodeLabel(selectedEdge.target_id) : ""}
              evidence={selectedEdge ? evidence[selectedEdge.id] ?? [] : []}
              proposal={state.proposal}
              running={state.status === "running"}
              onApprove={handleApprove}
              onSkip={skip}
              graphId={state.graph!.id}
              onGraphChanged={() => loadGraph(state.graph!.id)}
            />
          )}
        </ResizablePanel>
      </ResizablePanelGroup>
    );

  const content = (
    <div className="flex h-full flex-col">
      {topBar}
      <div className="min-h-0 flex-1">{body}</div>
    </div>
  );

  return (
    <ResizablePanelGroup
      direction="horizontal"
      className={cn(
        "h-full",
        // Animate only the two top-level panels (history + main); leave the nested
        // canvas/dossier group alone. Disabled while dragging so resize stays 1:1.
        "[&>[data-panel]]:transition-[flex] [&>[data-panel]]:duration-200 [&>[data-panel]]:ease-out",
        dragging && "[&>[data-panel]]:transition-none",
      )}
    >
      <Panel
        ref={historyRef}
        id="history"
        order={1}
        collapsible
        collapsedSize={0}
        minSize={14}
        maxSize={32}
        defaultSize={historyCollapsed ? 0 : 18}
        onCollapse={() => setHistoryCollapsed(true)}
        onExpand={() => setHistoryCollapsed(false)}
        className="min-w-0"
      >
        <HistorySidebar
          onOpenGraph={(id) => loadGraph(id)}
          onCollapse={() => historyRef.current?.collapse()}
          currentGraphId={state.graph?.id ?? null}
          onNewCanvas={handleNewCanvas}
        />
      </Panel>

      <ResizableHandle
        onDragging={setDragging}
        className={cn("bg-border transition-colors hover:bg-border-strong", historyCollapsed && "w-0")}
      />

      <ResizablePanel order={2} className="min-w-0">
        <div className="relative h-full">
          {historyCollapsed && (
            <button
              type="button"
              onClick={() => historyRef.current?.expand()}
              aria-label="Open history"
              title="Open history (⌘B)"
              className="absolute inset-y-0 left-0 z-20 flex w-3.5 items-center justify-center border-r border-border bg-background/70 text-muted-foreground/70 transition-colors hover:bg-surface-1 hover:text-foreground/90"
            >
              <PanelLeftOpen className="size-3.5" />
            </button>
          )}
          {content}
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
