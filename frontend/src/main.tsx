import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "next-themes";

import App from "./App.tsx";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { initDesktopChrome } from "./lib/desktopChrome";
import "./index.css";

// Before the first render: reserving the title-bar strip in an effect instead
// would paint one frame with the logo under the macOS traffic lights. No-op in
// a browser.
initDesktopChrome();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <BrowserRouter>
        <TooltipProvider delayDuration={300}>
          <App />
          <Toaster />
        </TooltipProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
