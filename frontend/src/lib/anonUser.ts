const KEY = "dogma:userId";
let cached: string | null = null;

/**
 * A stable anonymous user id (UUID), persisted to localStorage. Sent as the
 * `X-User-Id` header (and used as the userId path param) so the per-user context,
 * preferences, and conversation endpoints work for the local user until real auth
 * lands. Replace with the authenticated user id when auth is added.
 */
export function getAnonUserId(): string {
  if (cached) return cached;
  if (typeof localStorage === "undefined") {
    return "00000000-0000-4000-8000-000000000000";
  }
  let id = localStorage.getItem(KEY);
  if (!id) {
    id =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `00000000-0000-4000-8000-${Date.now().toString(16).padStart(12, "0").slice(-12)}`;
    localStorage.setItem(KEY, id);
  }
  cached = id;
  return id;
}
