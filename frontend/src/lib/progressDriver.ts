export type Phase = "upload" | "submitted" | "boot" | "inference" | "done";

export interface ProgressInput {
  phase: Phase;
  uploadFraction?: number;       // 0..1 during upload
  elapsedMs?: number;            // ms in the current phase
  lastStage?: string | null;     // STAGE: marker from logs
}

const STAGE_FLOOR: Record<string, number> = {
  loading_video: 0.65,
  tribe_inference: 0.75,
  scoring: 0.88,
  done: 0.95,
};

function asymptote(start: number, target: number, k: number, t: number): number {
  return target - (target - start) * Math.exp(-k * t);
}

export function computeProgress(input: ProgressInput): number {
  switch (input.phase) {
    case "upload":
      return Math.min(0.25, Math.max(0, (input.uploadFraction ?? 0) * 0.25));
    case "submitted":
      return 0.25;
    case "boot": {
      const t = (input.elapsedMs ?? 0) / 1000;
      return asymptote(0.25, 0.6, 0.04, t);
    }
    case "inference": {
      const t = (input.elapsedMs ?? 0) / 1000;
      const time = asymptote(0.6, 0.95, 0.025, t);
      const floor = input.lastStage ? STAGE_FLOOR[input.lastStage] ?? 0 : 0;
      return Math.max(time, floor);
    }
    case "done":
      return 1;
  }
}
