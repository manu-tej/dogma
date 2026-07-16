import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "../components/ui/button";

/**
 * Light/dark toggle backed by next-themes. The app currently ships dark-first
 * (its surfaces use hardcoded slate utilities), so this wires the theme
 * infrastructure; a fully-themed light palette is a later polish slice.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme !== "light";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={className}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
