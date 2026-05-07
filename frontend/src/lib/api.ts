import { getSessionId } from "./session";

export type JobStatus =
  | "queued"
  | "preprocessing"
  | "inferring"
  | "scoring"
  | "rendering"
  | "done"
  | "error";

export interface UploadResponse {
  job_id: string;
  attempt_id: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  stage_label: string;
  attempt_id: string | null;
  error_message: string | null;
}

export interface SubScores {
  reward: number;
  emotion: number;
  attention: number;
  novelty: number;
  social_relevance: number;
}

export interface TimelinePoint {
  t: number;
  reward: number;
  emotion: number;
  attention: number;
  novelty: number;
  social_relevance: number;
}

export interface AttemptResult {
  attempt_id: string;
  label: string;
  uploaded_at: string;
  status: string;
  video_filename: string;
  video_duration_s: number;
  headline_score: number | null;
  sub_scores: SubScores | null;
  timeline: TimelinePoint[] | null;
  has_brain_video: boolean;
  brain_frame_count: number;
  error_message: string | null;
}

export interface AttemptSummary {
  attempt_id: string;
  label: string;
  uploaded_at: string;
  status: string;
  headline_score: number | null;
  video_duration_s: number;
  has_brain_video: boolean;
}

export type CapabilityTier = "green" | "yellow" | "red";

export interface CapabilitiesResponse {
  tier: CapabilityTier;
  accelerator: "mps" | "cuda" | "cpu";
  accelerator_name: string;
  platform: string;
  total_memory_gb: number;
  available_memory_gb: number;
  bf16_supported: boolean;
  fp16_supported: boolean;
  tribev2_installed: boolean;
  hf_authenticated: boolean;
  recommended_dtype: string;
  active_backend: "mock" | "local" | "hosted";
  active_dtype: string;
  requested_backend: string;
  fallback_reason: string | null;
  can_run_local: boolean;
  warnings: string[];
}

async function req<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers || {});
  headers.set("X-Session-Id", getSessionId());
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text || path}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export const api = {
  async health() {
    return req<{ ok: boolean; backend: string; upload_max_bytes: number; upload_max_duration_s: number }>(
      "/api/health",
    );
  },
  async capabilities(): Promise<CapabilitiesResponse> {
    return req<CapabilitiesResponse>("/api/capabilities");
  },
  async upload(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("video", file);
    return req<UploadResponse>("/api/upload", { method: "POST", body: form });
  },
  async getJob(jobId: string): Promise<JobStatusResponse> {
    return req<JobStatusResponse>(`/api/jobs/${jobId}`);
  },
  async getAttempt(attemptId: string): Promise<AttemptResult> {
    return req<AttemptResult>(`/api/attempts/${attemptId}`);
  },
  async listAttempts(): Promise<AttemptSummary[]> {
    return req<AttemptSummary[]>(`/api/sessions/${getSessionId()}/attempts`);
  },
  async deleteAttempt(attemptId: string): Promise<void> {
    await req<{ ok: boolean }>(`/api/attempts/${attemptId}`, { method: "DELETE" });
  },
  videoUrl(attemptId: string): string {
    return `/api/attempts/${attemptId}/video`;
  },
  brainVideoUrl(attemptId: string): string {
    return `/api/attempts/${attemptId}/brain.mp4`;
  },
  thumbnailUrl(attemptId: string, second: number): string {
    return `/api/attempts/${attemptId}/thumbnails/${second}.jpg`;
  },
  brainFrameUrl(attemptId: string, frameIdx: number): string {
    return `/api/attempts/${attemptId}/brain-frames/${frameIdx}.jpg`;
  },
};
