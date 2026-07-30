import { HypothesisClient } from "../lib/hypothesis-client";

import { API_BASE_URL } from "@/lib/apiBaseUrl";

/** Process-wide client for the /hypothesis API. */
export const hypothesisClient = new HypothesisClient({ baseUrl: API_BASE_URL });

export { HypothesisClient };
