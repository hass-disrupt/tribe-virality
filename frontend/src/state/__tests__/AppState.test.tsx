import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { AppStateProvider, useAppState } from "../AppState";
import type { Attempt } from "../../types";

const wrap = ({ children }: { children: ReactNode }) => (
  <AppStateProvider>{children}</AppStateProvider>
);

const mkAttempt = (id: string, headline: number | null = null): Attempt => ({
  attemptId: id,
  predictionId: `pred_${id}`,
  label: id,
  videoBlobUrl: "blob:http://x/" + id,
  videoDurationS: 10,
  uploadedAt: "2026-05-08T00:00:00Z",
  status: "done",
  headlineScore: headline,
  subScores: null,
  timeline: null,
  frameCount: 0,
  modelVersion: null,
  scoringVersion: null,
  brainFrames: null,
  errorMessage: null,
});

describe("AppState", () => {
  it("starts with empty state", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    expect(result.current.state.apiKey).toBeNull();
    expect(result.current.state.attempts).toEqual([]);
    expect(result.current.state.currentJobId).toBeNull();
  });

  it("setApiKey stores key and account", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.setApiKey("r8_test", { username: "u", type: "user" }));
    expect(result.current.state.apiKey).toBe("r8_test");
    expect(result.current.state.apiKeyAccount?.username).toBe("u");
  });

  it("forgetKey clears apiKey, account, attempts, currentJobId", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => {
      result.current.setApiKey("r8_test", { username: "u", type: "user" });
      result.current.addAttempt(mkAttempt("v1"));
      result.current.setCurrentJob("pred_v1");
    });
    act(() => result.current.forgetKey());
    expect(result.current.state.apiKey).toBeNull();
    expect(result.current.state.apiKeyAccount).toBeNull();
    expect(result.current.state.attempts).toEqual([]);
    expect(result.current.state.currentJobId).toBeNull();
  });

  it("addAttempt prepends (newest first)", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => {
      result.current.addAttempt(mkAttempt("v1"));
      result.current.addAttempt(mkAttempt("v2"));
    });
    expect(result.current.state.attempts.map((a) => a.attemptId)).toEqual(["v2", "v1"]);
  });

  it("updateAttempt patches by attemptId", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.addAttempt(mkAttempt("v1")));
    act(() => result.current.updateAttempt("v1", { headlineScore: 72, status: "done" }));
    expect(result.current.state.attempts[0].headlineScore).toBe(72);
  });

  it("removeAttempt drops by id", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => {
      result.current.addAttempt(mkAttempt("v1"));
      result.current.addAttempt(mkAttempt("v2"));
    });
    act(() => result.current.removeAttempt("v1"));
    expect(result.current.state.attempts.map((a) => a.attemptId)).toEqual(["v2"]);
  });

  it("setCurrentJob stores prediction id", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.setCurrentJob("pred_xyz"));
    expect(result.current.state.currentJobId).toBe("pred_xyz");
  });
});
