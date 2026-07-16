import { Link } from "react-router-dom";
import { Compass } from "lucide-react";

import { Button } from "../components/ui/button";
import { EmptyState } from "../components/EmptyState";

/** Fallback for unknown routes. */
export function NotFound() {
  return (
    <EmptyState
      icon={Compass}
      title="Page not found"
      description="That destination doesn't exist. Use the sidebar or ⌘K to jump somewhere."
      action={
        <Button asChild>
          <Link to="/">Go home</Link>
        </Button>
      }
    />
  );
}
