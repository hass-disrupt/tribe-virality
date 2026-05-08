import { describe, it, expect } from "vitest";
import { computeProgress } from "../progressDriver";

describe("computeProgress", () => {
  it("uploads slice (0-25)", () => {
    const p = computeProgress({ phase: "upload", uploadFraction: 0.5 });
    expect(p).toBeCloseTo(0.125, 3);
  });

  it("upload fraction 1 snaps to 0.25", () => {
    const p = computeProgress({ phase: "upload", uploadFraction: 1 });
    expect(p).toBeCloseTo(0.25, 3);
  });

  it("submitted snaps to 0.25", () => {
    expect(computeProgress({ phase: "submitted" })).toBe(0.25);
  });

  it("boot crawl is monotonic and capped at 0.6", () => {
    let last = 0.25;
    for (let t = 0; t <= 90_000; t += 5_000) {
      const p = computeProgress({ phase: "boot", elapsedMs: t });
      expect(p).toBeGreaterThanOrEqual(last);
      expect(p).toBeLessThanOrEqual(0.6);
      last = p;
    }
  });

  it("inference crawl is monotonic and capped at 0.95", () => {
    let last = 0.6;
    for (let t = 0; t <= 120_000; t += 5_000) {
      const p = computeProgress({ phase: "inference", elapsedMs: t });
      expect(p).toBeGreaterThanOrEqual(last);
      expect(p).toBeLessThanOrEqual(0.95);
      last = p;
    }
  });

  it("inference stage 'scoring' bumps to >=0.85", () => {
    const p = computeProgress({ phase: "inference", elapsedMs: 0, lastStage: "scoring" });
    expect(p).toBeGreaterThanOrEqual(0.85);
  });

  it("done is 1", () => {
    expect(computeProgress({ phase: "done" })).toBe(1);
  });
});
