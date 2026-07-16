import { useCallback, useEffect, useRef, useState } from "react";
import { buildWorkflowFromPlan, type EvaluationWorkflow } from "../lib/hypothesis-ui/workflow";
import type { EvaluationPlan } from "../lib/hypothesis-client/types";

export function useEvaluationWorkflow(
  edgeId: string,
  getPlan: (edgeId: string) => Promise<EvaluationPlan>,
  resolvePlan: (edgeId: string) => Promise<EvaluationPlan>,
) {
  const [workflow, setWorkflow] = useState<EvaluationWorkflow | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "resolving" | "error">("loading");
  const currentEdgeIdRef = useRef(edgeId);
  useEffect(() => { currentEdgeIdRef.current = edgeId; }, [edgeId]);

  useEffect(() => {
    let live = true;
    setStatus("loading");
    getPlan(edgeId)
      .then((p) => {
        if (live) {
          setWorkflow(buildWorkflowFromPlan(p));
          setStatus("ready");
        }
      })
      .catch(() => {
        if (live) setStatus("error");
      });
    return () => {
      live = false;
    };
  }, [edgeId, getPlan]);

  const resolve = useCallback(() => {
    const resolvedFor = edgeId;
    setStatus("resolving");
    resolvePlan(edgeId)
      .then((p) => {
        if (currentEdgeIdRef.current === resolvedFor) {
          setWorkflow(buildWorkflowFromPlan(p));
          setStatus("ready");
        }
      })
      .catch(() => {
        if (currentEdgeIdRef.current === resolvedFor) setStatus("error");
      });
  }, [edgeId, resolvePlan]);

  return { workflow, status, resolve };
}
