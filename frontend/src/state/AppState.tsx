import { createContext, useCallback, useContext, useMemo, useReducer } from "react";
import type { ReactNode } from "react";
import type { Attempt, ReplicateAccount } from "../types";

interface AppStateData {
  apiKey: string | null;
  apiKeyAccount: ReplicateAccount | null;
  attempts: Attempt[];
  currentJobId: string | null;
}

const INITIAL: AppStateData = {
  apiKey: null,
  apiKeyAccount: null,
  attempts: [],
  currentJobId: null,
};

type Action =
  | { type: "SET_KEY"; key: string; account: ReplicateAccount }
  | { type: "FORGET_KEY" }
  | { type: "ADD_ATTEMPT"; attempt: Attempt }
  | { type: "UPDATE_ATTEMPT"; id: string; patch: Partial<Attempt> }
  | { type: "REMOVE_ATTEMPT"; id: string }
  | { type: "SET_CURRENT_JOB"; jobId: string | null };

function reducer(state: AppStateData, action: Action): AppStateData {
  switch (action.type) {
    case "SET_KEY":
      return { ...state, apiKey: action.key, apiKeyAccount: action.account };
    case "FORGET_KEY":
      for (const a of state.attempts) {
        if (a.videoBlobUrl) URL.revokeObjectURL(a.videoBlobUrl);
      }
      return { ...INITIAL };
    case "ADD_ATTEMPT":
      return { ...state, attempts: [action.attempt, ...state.attempts] };
    case "UPDATE_ATTEMPT":
      return {
        ...state,
        attempts: state.attempts.map((a) =>
          a.attemptId === action.id ? { ...a, ...action.patch } : a,
        ),
      };
    case "REMOVE_ATTEMPT": {
      const target = state.attempts.find((a) => a.attemptId === action.id);
      if (target?.videoBlobUrl) URL.revokeObjectURL(target.videoBlobUrl);
      return {
        ...state,
        attempts: state.attempts.filter((a) => a.attemptId !== action.id),
      };
    }
    case "SET_CURRENT_JOB":
      return { ...state, currentJobId: action.jobId };
  }
}

interface AppStateContextValue {
  state: AppStateData;
  setApiKey: (key: string, account: ReplicateAccount) => void;
  forgetKey: () => void;
  addAttempt: (attempt: Attempt) => void;
  updateAttempt: (id: string, patch: Partial<Attempt>) => void;
  removeAttempt: (id: string) => void;
  setCurrentJob: (jobId: string | null) => void;
}

const AppStateContext = createContext<AppStateContextValue | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, INITIAL);

  const setApiKey = useCallback(
    (key: string, account: ReplicateAccount) =>
      dispatch({ type: "SET_KEY", key, account }),
    [],
  );
  const forgetKey = useCallback(() => dispatch({ type: "FORGET_KEY" }), []);
  const addAttempt = useCallback(
    (attempt: Attempt) => dispatch({ type: "ADD_ATTEMPT", attempt }),
    [],
  );
  const updateAttempt = useCallback(
    (id: string, patch: Partial<Attempt>) =>
      dispatch({ type: "UPDATE_ATTEMPT", id, patch }),
    [],
  );
  const removeAttempt = useCallback(
    (id: string) => dispatch({ type: "REMOVE_ATTEMPT", id }),
    [],
  );
  const setCurrentJob = useCallback(
    (jobId: string | null) => dispatch({ type: "SET_CURRENT_JOB", jobId }),
    [],
  );

  const value = useMemo(
    () => ({ state, setApiKey, forgetKey, addAttempt, updateAttempt, removeAttempt, setCurrentJob }),
    [state, setApiKey, forgetKey, addAttempt, updateAttempt, removeAttempt, setCurrentJob],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used inside <AppStateProvider>");
  return ctx;
}
