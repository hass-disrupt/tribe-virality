import { useEffect, useRef, useState } from "react";
import { useAppState } from "../state/AppState";
import { getPrediction, type PredictionStatus } from "../lib/replicate";

interface PollResult extends PredictionStatus {
  elapsedMs: number;
  lastStage: string | null;
}

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);

function pollIntervalMs(elapsedMs: number): number {
  if (elapsedMs < 30_000) return 1500;
  if (elapsedMs < 120_000) return 2500;
  return 4000;
}

function lastStageFromLogs(logs: string | null): string | null {
  if (!logs) return null;
  const matches = [...logs.matchAll(/STAGE:([a-z_]+)/g)];
  return matches.length ? matches[matches.length - 1][1] : null;
}

export function usePredictionPolling(predictionId: string | null): PollResult {
  const { state } = useAppState();
  const startRef = useRef(Date.now());
  const [snapshot, setSnapshot] = useState<PollResult>({
    id: predictionId ?? "",
    status: "starting",
    logs: null,
    output: null,
    error: null,
    elapsedMs: 0,
    lastStage: null,
  });

  useEffect(() => {
    if (!predictionId || !state.apiKey) return;
    let cancelled = false;
    let timer: number | null = null;
    let backoff = 0;
    startRef.current = Date.now();

    async function tick() {
      if (cancelled) return;
      try {
        const status = await getPrediction({ apiKey: state.apiKey! }, predictionId!);
        backoff = 0;
        const elapsedMs = Date.now() - startRef.current;
        const lastStage = lastStageFromLogs(status.logs);
        setSnapshot({ ...status, elapsedMs, lastStage });
        if (TERMINAL.has(status.status)) return;
        timer = window.setTimeout(tick, pollIntervalMs(elapsedMs));
      } catch {
        backoff = Math.min(backoff + 1, 3);
        timer = window.setTimeout(tick, 2000 * Math.pow(2, backoff));
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [predictionId, state.apiKey]);

  return snapshot;
}
