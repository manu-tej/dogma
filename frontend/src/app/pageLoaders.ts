/**
 * Lazy page-chunk loaders, keyed by route path. The same dynamic-import specifiers
 * are used by App.tsx's React.lazy calls, so warming a chunk here (on hover/focus)
 * means the chunk is already in memory by the time the user clicks — navigation
 * feels instant. Vite dedupes identical dynamic imports, so prefetch + lazy share
 * one chunk and one in-flight promise.
 */
const loaders: Record<string, () => Promise<unknown>> = {
  "/": () => import("../pages/HomePage"),
  "/canvas": () => import("../pages/CanvasPage"),
  "/chat": () => import("../pages/ChatPage"),
  "/datasets": () => import("../pages/DatasetsPage"),
  "/methods": () => import("../pages/MethodsPage"),
  "/pipelines": () => import("../pages/PipelinesPage"),
  "/interpretation": () => import("../pages/InterpretationPage"),
  "/settings": () => import("../pages/SettingsPage"),
};

const prefetched = new Set<string>();

/** Warm the chunk for a route (idempotent). Safe to call on hover/focus. */
export function prefetchRoute(path: string): void {
  const loader = loaders[path];
  if (!loader || prefetched.has(path)) return;
  prefetched.add(path);
  loader().catch(() => prefetched.delete(path));
}
