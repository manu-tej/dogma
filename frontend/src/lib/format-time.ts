/**
 * Format an ISO 8601 timestamp as a human-readable relative or absolute string.
 *
 * @param iso   - The ISO timestamp string to format (handles microseconds + tz offsets).
 * @param now   - Reference point for "now"; defaults to `new Date()`. Inject in tests for determinism.
 * @returns     - A relative string ("just now", "5m ago", …) for recent timestamps,
 *               or a locale-formatted absolute string for older ones.
 *               Returns the original string unchanged if it cannot be parsed.
 */
export function formatTimestamp(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return iso;

  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1_000);
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHour = Math.floor(diffMs / 3_600_000);
  const diffDay = Math.floor(diffMs / 86_400_000);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
