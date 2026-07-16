import type {
  ClarifyingQuestion, SeedAnswer, SeedingStep, SeedSkeleton,
} from "../lib/hypothesis-client";

export type SeedingStatus =
  | "idle" | "seeding" | "clarifying" | "proposing" | "building" | "error";

export interface SeedingState {
  status: SeedingStatus;
  query: string;
  answers: SeedAnswer[];
  questions: ClarifyingQuestion[];
  skeleton: SeedSkeleton | null;
  error: string | null;
}

export const initialSeedingState: SeedingState = {
  status: "idle", query: "", answers: [], questions: [], skeleton: null, error: null,
};

export type SeedingAction =
  | { type: "QUERY_SUBMIT"; query: string }
  | { type: "STEP"; step: SeedingStep }
  | { type: "ANSWER"; answer: SeedAnswer }
  | { type: "DROP_NODE"; nodeId: string }
  | { type: "BUILD_START" }
  | { type: "ERROR"; message: string };

export function seedingReducer(state: SeedingState, action: SeedingAction): SeedingState {
  switch (action.type) {
    case "QUERY_SUBMIT":
      return { ...initialSeedingState, status: "seeding", query: action.query };
    case "STEP":
      return action.step.kind === "questions"
        ? { ...state, status: "clarifying", questions: action.step.questions, error: null }
        : { ...state, status: "proposing", skeleton: action.step.skeleton, error: null };
    case "ANSWER": {
      const answers = [
        ...state.answers.filter((a) => a.question_id !== action.answer.question_id),
        action.answer,
      ];
      return { ...state, answers, status: "seeding" };
    }
    case "DROP_NODE": {
      if (!state.skeleton) return state;
      const nodes = state.skeleton.nodes.filter((n) => n.id !== action.nodeId);
      const edges = state.skeleton.edges.filter(
        (e) => e.source_id !== action.nodeId && e.target_id !== action.nodeId,
      );
      return { ...state, skeleton: { ...state.skeleton, nodes, edges } };
    }
    case "BUILD_START":
      return { ...state, status: "building", error: null };
    case "ERROR":
      // Toast already surfaced the message; return to an actionable state so the
      // UI never gets stuck in a disabled "building"/"seeding" spinner.
      return {
        ...state,
        error: action.message,
        status: state.skeleton ? "proposing" : state.questions.length ? "clarifying" : "idle",
      };
    default:
      return state;
  }
}
