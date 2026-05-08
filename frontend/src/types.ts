export type SubScoreKey =
  | "reward"
  | "emotion"
  | "attention"
  | "novelty"
  | "social_relevance";

export const SUB_SCORE_KEYS: readonly SubScoreKey[] = [
  "reward",
  "emotion",
  "attention",
  "novelty",
  "social_relevance",
] as const;

export type SubScores = Record<SubScoreKey, number>;

export interface TimelinePoint extends SubScores {
  t: number;
}

export type AttemptStatus = "queued" | "processing" | "done" | "error";

export interface Attempt {
  attemptId: string;
  predictionId: string;
  label: string;
  videoBlobUrl: string;
  videoDurationS: number;
  uploadedAt: string;
  status: AttemptStatus;
  headlineScore: number | null;
  subScores: SubScores | null;
  timeline: TimelinePoint[] | null;
  frameCount: number;
  modelVersion: string | null;
  scoringVersion: string | null;
  brainFrames: string[] | null;
  errorMessage: string | null;
}

export interface ReplicateAccount {
  username: string;
  type: string;
}
