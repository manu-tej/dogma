import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "../components/ui/button";

interface Props {
  children: ReactNode;
  /** Changing this key resets the boundary (e.g. on route change). */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

/**
 * A classic error boundary wrapping the routed content area so a single page's
 * render crash shows a recoverable panel instead of a blank screen.
 */
export class RouteError extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    // Reset on navigation so a recovered route renders normally.
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Route render error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <div className="elev rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-destructive">
          <AlertTriangle className="h-7 w-7" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">Something went wrong on this page</h2>
        <p className="max-w-md text-sm text-muted-foreground">{this.state.error.message}</p>
        <div className="mt-2 flex gap-2">
          <Button variant="outline" onClick={() => this.setState({ error: null })}>
            Try again
          </Button>
          <Button onClick={() => (window.location.href = "/")}>Go home</Button>
        </div>
      </div>
    );
  }
}
