/**
 * Single source of truth for the backend base URL.
 *
 * Call sites previously read either `VITE_GEO_API_URL` or `VITE_API_URL`,
 * depending on which service they lived in, so pointing the app at a backend
 * meant setting both and hoping none were missed.
 *
 * Resolution order, most specific first:
 *
 *   1. `window.dogma.apiBaseUrl` — injected by the Electron preload. The
 *      desktop app needs this at *runtime*, because one `frontend/build`
 *      artifact serves both the web and desktop surfaces, and because the
 *      desktop backend must be addressed as 127.0.0.1 rather than localhost
 *      (uvicorn binds the IPv4 loopback; "localhost" may resolve to ::1 first
 *      and fail to connect).
 *   2. `VITE_API_URL`, then `VITE_GEO_API_URL` — build-time configuration.
 *   3. The local development default.
 */

export const DEFAULT_API_BASE_URL = "http://localhost:8000";

declare global {
  interface Window {
    dogma?: {
      isDesktop?: boolean;
      apiBaseUrl?: string | null;
      platform?: string;
      /** Strip to keep clear of the macOS traffic lights; 0 with normal chrome. */
      titlebarInset?: number;
    };
  }
}

type EnvLike = Record<string, string | boolean | undefined>;

function firstNonEmpty(
  ...candidates: Array<string | null | undefined>
): string | null {
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim() !== "") {
      // A trailing slash would produce "…//health" once a path is appended.
      return candidate.trim().replace(/\/+$/, "");
    }
  }
  return null;
}

/**
 * Pure resolver, exported for tests.
 *
 * @param desktopBaseUrl Value supplied by the Electron preload, if any.
 * @param env Build-time environment values.
 */
export function resolveApiBaseUrl(
  desktopBaseUrl?: string | null,
  env: EnvLike = {},
): string {
  return (
    firstNonEmpty(
      desktopBaseUrl,
      typeof env.VITE_API_URL === "string" ? env.VITE_API_URL : undefined,
      typeof env.VITE_GEO_API_URL === "string"
        ? env.VITE_GEO_API_URL
        : undefined,
    ) ?? DEFAULT_API_BASE_URL
  );
}

function currentEnv(): EnvLike {
  try {
    return (import.meta.env ?? {}) as EnvLike;
  } catch {
    return {};
  }
}

function desktopBaseUrl(): string | null {
  if (typeof window === "undefined") return null;
  return window.dogma?.apiBaseUrl ?? null;
}

/**
 * Resolved once at module load. The preload runs before any renderer script,
 * so `window.dogma` is already populated by the time this evaluates.
 */
export const API_BASE_URL = resolveApiBaseUrl(desktopBaseUrl(), currentEnv());

/** True when running inside the Electron shell rather than a browser. */
export const IS_DESKTOP =
  typeof window !== "undefined" && window.dogma?.isDesktop === true;
