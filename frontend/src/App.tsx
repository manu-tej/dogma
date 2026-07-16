import { lazy } from "react";
import { Routes, Route } from "react-router-dom";

import { AppShell } from "./app/AppShell";
import { NotFound } from "./app/NotFound";

// Route-level code-splitting: each destination is its own chunk, so the initial
// load stays small and heavy pages (canvas/React-Flow, charts) load on demand.
// (Pages are named exports, so map them to the default React.lazy expects.)
const HomePage = lazy(() => import("./pages/HomePage").then((m) => ({ default: m.HomePage })));
const CanvasPage = lazy(() => import("./pages/CanvasPage").then((m) => ({ default: m.CanvasPage })));
const ChatPage = lazy(() => import("./pages/ChatPage").then((m) => ({ default: m.ChatPage })));
const DatasetsPage = lazy(() => import("./pages/DatasetsPage").then((m) => ({ default: m.DatasetsPage })));
const MethodsPage = lazy(() => import("./pages/MethodsPage").then((m) => ({ default: m.MethodsPage })));
const PipelinesPage = lazy(() => import("./pages/PipelinesPage").then((m) => ({ default: m.PipelinesPage })));
const InterpretationPage = lazy(() =>
  import("./pages/InterpretationPage").then((m) => ({ default: m.InterpretationPage })),
);
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));

/**
 * The dogma app is a routed shell: a single layout route (AppShell) renders the
 * persistent nav + top bar, and every destination renders through its <Outlet/>.
 */
export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="canvas" element={<CanvasPage />} />
        <Route path="canvas/:graphId" element={<CanvasPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="chat/:conversationId" element={<ChatPage />} />
        <Route path="datasets" element={<DatasetsPage />} />
        <Route path="methods" element={<MethodsPage />} />
        <Route path="pipelines" element={<PipelinesPage />} />
        <Route path="interpretation" element={<InterpretationPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
