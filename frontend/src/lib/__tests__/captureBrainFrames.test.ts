import { describe, it, expect, vi } from "vitest";
import { captureBrainFramesWithRenderer } from "../captureBrainFrames";
import type { TimelinePoint } from "../../types";

const fakeTimeline: TimelinePoint[] = Array.from({ length: 5 }, (_, i) => ({
  t: i,
  reward: 50, emotion: 50, attention: 50, novelty: 50, social_relevance: 50,
}));

describe("captureBrainFramesWithRenderer", () => {
  it("returns one data URL per requested frame", async () => {
    const renderFrame = vi.fn(async (_t: number) =>
      "data:image/jpeg;base64,/9j/AAAA",
    );
    const out = await captureBrainFramesWithRenderer({
      timeline: fakeTimeline,
      frameCount: 4,
      totalDurationS: 4,
      renderFrame,
    });
    expect(out).toHaveLength(4);
    expect(renderFrame).toHaveBeenCalledTimes(4);
    expect(out.every((s) => s.startsWith("data:image/"))).toBe(true);
  });

  it("evenly spaces timestamps from 0 to totalDurationS", async () => {
    const seen: number[] = [];
    const renderFrame = vi.fn(async (t: number) => { seen.push(t); return "data:image/jpeg;base64,X"; });
    await captureBrainFramesWithRenderer({
      timeline: fakeTimeline,
      frameCount: 3,
      totalDurationS: 10,
      renderFrame,
    });
    expect(seen).toEqual([0, 5, 10]);
  });
});
