import type { TimelinePoint } from "../types";

export interface CaptureWithRendererInput {
  timeline: TimelinePoint[];
  frameCount: number;
  totalDurationS: number;
  renderFrame: (timeS: number) => Promise<string>;
}

export async function captureBrainFramesWithRenderer(
  input: CaptureWithRendererInput,
): Promise<string[]> {
  const { frameCount, totalDurationS, renderFrame } = input;
  if (frameCount <= 0) return [];
  const out: string[] = [];
  for (let i = 0; i < frameCount; i++) {
    const t = frameCount === 1 ? 0 : (i * totalDurationS) / (frameCount - 1);
    out.push(await renderFrame(t));
  }
  return out;
}
