import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Brain, TrendingUp, Zap } from "lucide-react";
import { DropZone } from "../components/DropZone";
import { useAppState } from "../state/AppState";
import {
  uploadFile,
  createPrediction,
  getLatestModelVersion,
  ReplicateAuthError,
  ReplicateQuotaError,
} from "../lib/replicate";
import { REPLICATE_MODEL } from "../lib/replicateConstants";
import type { Attempt } from "../types";

function nextLabel(existingCount: number): string {
  return `v${existingCount + 1}`;
}

function newAttemptId(): string {
  return crypto.randomUUID();
}

async function readDuration(file: File): Promise<number> {
  const url = URL.createObjectURL(file);
  try {
    return await new Promise<number>((resolve, reject) => {
      const v = document.createElement("video");
      v.preload = "metadata";
      v.onloadedmetadata = () => resolve(v.duration);
      v.onerror = () => reject(new Error("metadata"));
      v.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function Landing() {
  const navigate = useNavigate();
  const { state, addAttempt, setCurrentJob, forgetKey } = useAppState();
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    if (!state.apiKey) return;
    setBusy(true);
    try {
      setStage("Reading video…");
      const duration = await readDuration(file);

      const attemptId = newAttemptId();
      const blobUrl = URL.createObjectURL(file);
      const label = nextLabel(state.attempts.length);

      setStage("Uploading to Replicate…");
      const uploaded = await uploadFile({ apiKey: state.apiKey }, file);

      setStage("Resolving model version…");
      const version = await getLatestModelVersion(
        { apiKey: state.apiKey },
        REPLICATE_MODEL.owner,
        REPLICATE_MODEL.name,
      );

      setStage("Submitting prediction…");
      const prediction = await createPrediction(
        { apiKey: state.apiKey },
        { version, input: { video: uploaded.url } },
      );

      const attempt: Attempt = {
        attemptId,
        predictionId: prediction.id,
        label,
        videoBlobUrl: blobUrl,
        videoDurationS: duration,
        uploadedAt: new Date().toISOString(),
        status: "queued",
        headlineScore: null,
        subScores: null,
        timeline: null,
        frameCount: 0,
        modelVersion: null,
        scoringVersion: null,
        brainFrames: null,
        errorMessage: null,
      };
      addAttempt(attempt);
      setCurrentJob(prediction.id);
      navigate(`/processing/${prediction.id}`);
    } catch (e) {
      if (e instanceof ReplicateAuthError) {
        forgetKey();
        setError("Token rejected by Replicate. Please re-enter it.");
      } else if (e instanceof ReplicateQuotaError) {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : "Upload failed.");
      }
    } finally {
      setBusy(false);
      setStage("");
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-16 flex flex-col items-center gap-12">
      <div className="text-center flex flex-col gap-4">
        <h1 className="text-4xl font-bold tracking-tight text-ink">
          How viral will your video be?
        </h1>
        <p className="text-ink-muted text-lg leading-relaxed max-w-xl">
          Upload your content and see how a human brain would respond — predicted
          by Meta's TRIBE v2 foundation model.
        </p>
        <p className="text-ink-dim text-xs">
          ~$0.05–0.20 per prediction · billed to your Replicate account
        </p>
      </div>

      <DropZone onFile={handleFile} disabled={busy} />
      {busy && <p className="text-accent text-sm -mt-6">{stage}</p>}
      {error && <p className="text-bad text-sm -mt-6">{error}</p>}

      <div className="w-full grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { icon: <Zap className="w-5 h-5 text-accent" />, title: "Upload", body: "Drop any MP4, MOV, or WebM up to 60s." },
          { icon: <Brain className="w-5 h-5 text-accent" />, title: "Predict", body: "TRIBE v2 predicts fMRI brain activity frame by frame." },
          { icon: <TrendingUp className="w-5 h-5 text-accent" />, title: "Score", body: "See your virality score and edit to improve it." },
        ].map(({ icon, title, body }) => (
          <div key={title} className="card p-5 flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
              {icon}
            </div>
            <p className="font-medium text-sm text-ink">{title}</p>
            <p className="text-xs text-ink-muted leading-relaxed">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
