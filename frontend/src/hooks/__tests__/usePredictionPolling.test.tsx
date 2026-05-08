import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { AppStateProvider, useAppState } from "../../state/AppState";
import { usePredictionPolling } from "../usePredictionPolling";
import type { PredictionStatus } from "../../lib/replicate";

function Wrap({ children }: { children: ReactNode }) {
  return <AppStateProvider>{children}</AppStateProvider>;
}

function useSeededState() {
  const ctx = useAppState();
  if (!ctx.state.apiKey) ctx.setApiKey("r8_test", { username: "u", type: "user" });
  return ctx;
}

const mkStatus = (status: PredictionStatus["status"], logs: string | null = null): PredictionStatus => ({
  id: "pred_1",
  status,
  logs,
  output: status === "succeeded"
    ? { headline_score: 50, sub_scores: {}, timeline: [], video_duration_s: 1, frame_count: 0, model_version: "x", scoring_version: "1" }
    : null,
  error: null,
});

describe("usePredictionPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls until succeeded and returns terminal output", async () => {
    const states = [mkStatus("starting"), mkStatus("processing"), mkStatus("succeeded")];
    let i = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify(states[Math.min(i++, states.length - 1)]), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const { result } = renderHook(
      () => {
        useSeededState();
        return usePredictionPolling("pred_1");
      },
      { wrapper: Wrap },
    );
    for (let n = 0; n < 30; n++) {
      await vi.advanceTimersByTimeAsync(1500);
      if (result.current.status === "succeeded") break;
    }
    expect(result.current.status).toBe("succeeded");
    expect(result.current.error).toBeNull();
  });

  it("stops polling once status is terminal", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mkStatus("succeeded")), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    renderHook(
      () => {
        useSeededState();
        return usePredictionPolling("pred_1");
      },
      { wrapper: Wrap },
    );
    await vi.advanceTimersByTimeAsync(1500);
    const callsAfterFirst = fetchSpy.mock.calls.length;
    await vi.advanceTimersByTimeAsync(20_000);
    expect(fetchSpy.mock.calls.length).toBe(callsAfterFirst);
  });

  it("exposes the latest STAGE: line from logs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify(mkStatus("processing", "boot ok\nSTAGE:tribe_inference\nworking…")),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const { result } = renderHook(
      () => {
        useSeededState();
        return usePredictionPolling("pred_1");
      },
      { wrapper: Wrap },
    );
    for (let n = 0; n < 10; n++) {
      await vi.advanceTimersByTimeAsync(1500);
      if (result.current.lastStage === "tribe_inference") break;
    }
    expect(result.current.lastStage).toBe("tribe_inference");
  });
});
