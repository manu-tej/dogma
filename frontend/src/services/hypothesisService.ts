import { HypothesisClient } from "../lib/hypothesis-client";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const API_BASE_URL: string =
  ((import.meta as any).env?.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

/** Process-wide client for the /hypothesis API. */
export const hypothesisClient = new HypothesisClient({ baseUrl: API_BASE_URL });

export { HypothesisClient };
