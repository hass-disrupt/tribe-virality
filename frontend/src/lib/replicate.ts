const REPLICATE_HOST = "https://api.replicate.com";

export class ReplicateAuthError extends Error {
  constructor(msg: string) { super(msg); this.name = "ReplicateAuthError"; }
}
export class ReplicateQuotaError extends Error {
  constructor(msg: string) { super(msg); this.name = "ReplicateQuotaError"; }
}
export class ReplicateNetworkError extends Error {
  constructor(msg: string) { super(msg); this.name = "ReplicateNetworkError"; }
}

interface AuthCtx { apiKey: string }

function scrub(msg: string): string {
  return msg
    .replace(/Bearer\s+r8_[A-Za-z0-9_-]+/g, "Bearer ***")
    .replace(/r8_[A-Za-z0-9_-]{6,}/g, "r8_***")
    .replace(/Authorization:[^,)\]]+/gi, "Authorization: ***");
}

export async function replicateFetch(
  auth: AuthCtx,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = `${REPLICATE_HOST}${path}`;
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${auth.apiKey}`);

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new ReplicateNetworkError(scrub(`Network error: ${msg}`));
  }

  if (res.status === 401 || res.status === 403) {
    throw new ReplicateAuthError(`Replicate rejected the token (${res.status}).`);
  }
  if (res.status === 402) {
    throw new ReplicateQuotaError("Replicate says you're out of credits. Add some at replicate.com/account/billing.");
  }
  if (res.status >= 500) {
    throw new ReplicateNetworkError(`Replicate is having trouble (${res.status}). Try again.`);
  }
  return res;
}

export async function validateToken(apiKey: string): Promise<{ username: string; type: string }> {
  const res = await replicateFetch({ apiKey }, "/v1/account");
  if (!res.ok) {
    throw new ReplicateNetworkError(`Account check failed (${res.status}).`);
  }
  const json = await res.json();
  return { username: String(json.username ?? ""), type: String(json.type ?? "") };
}

export interface UploadedFile {
  id: string;
  url: string;
}

export async function uploadFile(
  auth: AuthCtx,
  file: File,
  onProgress?: (loaded: number, total: number) => void,
): Promise<UploadedFile> {
  return new Promise<UploadedFile>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${REPLICATE_HOST}/v1/files`);
    xhr.setRequestHeader("Authorization", `Bearer ${auth.apiKey}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded, e.total);
    };
    xhr.onerror = () => reject(new ReplicateNetworkError("Upload failed (network error)."));
    xhr.onload = () => {
      if (xhr.status === 401 || xhr.status === 403) {
        reject(new ReplicateAuthError("Replicate rejected the token during upload."));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const json = JSON.parse(xhr.responseText);
          resolve({ id: String(json.id ?? ""), url: String(json.urls?.get ?? "") });
        } catch {
          reject(new ReplicateNetworkError("Bad response from Replicate Files API."));
        }
      } else {
        reject(new ReplicateNetworkError(`Upload failed (${xhr.status}).`));
      }
    };
    const fd = new FormData();
    fd.append("content", file);
    xhr.send(fd);
  });
}

export interface PredictionStatus {
  id: string;
  status: "starting" | "processing" | "succeeded" | "failed" | "canceled";
  logs: string | null;
  output: unknown;
  error: string | null;
  metrics?: { predict_time?: number };
}

export async function getLatestModelVersion(
  auth: AuthCtx,
  owner: string,
  name: string,
): Promise<string> {
  const res = await replicateFetch(auth, `/v1/models/${owner}/${name}`);
  if (!res.ok) throw new ReplicateNetworkError(`Failed to fetch model (${res.status}).`);
  const json = await res.json();
  const version = json?.latest_version?.id;
  if (!version) throw new ReplicateNetworkError("Model has no published version.");
  return String(version);
}

export async function createPrediction(
  auth: AuthCtx,
  body: { version: string; input: Record<string, unknown> },
): Promise<PredictionStatus> {
  const res = await replicateFetch(auth, "/v1/predictions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ReplicateNetworkError(`Could not create prediction (${res.status}).`);
  return (await res.json()) as PredictionStatus;
}

export async function getPrediction(
  auth: AuthCtx,
  predictionId: string,
): Promise<PredictionStatus> {
  const res = await replicateFetch(auth, `/v1/predictions/${predictionId}`);
  if (!res.ok) throw new ReplicateNetworkError(`Could not fetch prediction (${res.status}).`);
  return (await res.json()) as PredictionStatus;
}

export async function cancelPrediction(
  auth: AuthCtx,
  predictionId: string,
): Promise<void> {
  await replicateFetch(auth, `/v1/predictions/${predictionId}/cancel`, { method: "POST" });
}
