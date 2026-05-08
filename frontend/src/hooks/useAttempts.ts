import { useAppState } from "../state/AppState";
import type { Attempt } from "../types";

export function useAttempts(): {
  attempts: Attempt[];
  remove: (id: string) => void;
} {
  const { state, removeAttempt } = useAppState();
  return { attempts: state.attempts, remove: removeAttempt };
}
