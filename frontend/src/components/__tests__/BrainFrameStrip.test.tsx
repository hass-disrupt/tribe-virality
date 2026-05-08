import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrainFrameStrip } from "../BrainFrameStrip";
import type { TimelinePoint } from "../../types";

const TL: TimelinePoint[] = Array.from({ length: 4 }, (_, i) => ({
  t: i,
  reward: 50, emotion: 50, attention: 50, novelty: 50, social_relevance: 50,
}));

describe("BrainFrameStrip", () => {
  it("renders one image per provided brainFrame and thumbnail", () => {
    render(
      <BrainFrameStrip
        brainFrames={["data:image/jpeg;base64,1", "data:image/jpeg;base64,2"]}
        thumbnails={["data:image/jpeg;base64,a", "data:image/jpeg;base64,b", "data:image/jpeg;base64,c"]}
        timeline={TL}
        totalDuration={2}
        frameCount={2}
        playheadTime={0}
      />,
    );
    const imgs = screen.getAllByRole("img");
    // 3 thumbnails + 2 brain frames = 5 imgs total.
    expect(imgs.length).toBe(5);
  });
});
