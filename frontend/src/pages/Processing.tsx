import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAppState } from "../state/AppState";
import { usePredictionPolling } from "../hooks/usePredictionPolling";
import { computeProgress, type Phase } from "../lib/progressDriver";
import { cancelPrediction, ReplicateAuthError } from "../lib/replicate";
import type { TimelinePoint, SubScores } from "../types";

interface CogOutput {
  headline_score: number;
  sub_scores: SubScores;
  timeline: TimelinePoint[];
  video_duration_s: number;
  frame_count: number;
  model_version: string;
  scoring_version: string;
}

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export default function Processing() {
  const { predictionId = "" } = useParams<{ predictionId: string }>();
  const navigate = useNavigate();
  const { state, updateAttempt, forgetKey, setCurrentJob } = useAppState();
  const poll = usePredictionPolling(predictionId);
  const [phaseStartMs, setPhaseStartMs] = useState<number>(Date.now());
  const [phase, setPhase] = useState<Phase>("submitted");
  const [now, setNow] = useState(Date.now());
  const cancelledRef = useRef(false);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (poll.status === "starting" && phase !== "boot") {
      setPhase("boot");
      setPhaseStartMs(Date.now());
    } else if (poll.status === "processing" && phase !== "inference") {
      setPhase("inference");
      setPhaseStartMs(Date.now());
    } else if (poll.status === "succeeded" && phase !== "done") {
      setPhase("done");
    }
  }, [poll.status, phase]);

  const attempt = useMemo(
    () => state.attempts.find((a) => a.predictionId === predictionId) ?? null,
    [state.attempts, predictionId],
  );

  useEffect(() => {
    if (!attempt || cancelledRef.current) return;
    if (poll.status === "succeeded" && poll.output) {
      const out = poll.output as CogOutput;
      updateAttempt(attempt.attemptId, {
        status: "done",
        headlineScore: out.headline_score,
        subScores: out.sub_scores,
        timeline: out.timeline,
        frameCount: out.frame_count,
        modelVersion: out.model_version,
        scoringVersion: out.scoring_version,
      });
      setCurrentJob(null);
      navigate(`/results/${attempt.attemptId}`);
    } else if (poll.status === "failed") {
      updateAttempt(attempt.attemptId, {
        status: "error",
        errorMessage: poll.error ?? "Prediction failed.",
      });
      setCurrentJob(null);
    }
  }, [poll.status, poll.output, poll.error, attempt, navigate, updateAttempt, setCurrentJob]);

  useEffect(() => {
    if (poll.status === "succeeded" || poll.status === "failed" || poll.status === "canceled") return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "A prediction is running. If you leave, you'll lose track of it but Replicate will still charge for the run.";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [poll.status]);

  const elapsedInPhaseMs = now - phaseStartMs;
  const totalElapsedMs = poll.elapsedMs;

  const fraction = computeProgress({
    phase,
    elapsedMs: elapsedInPhaseMs,
    lastStage: poll.lastStage,
  });

  const isColdStart = poll.status === "starting" && totalElapsedMs > 15_000;

  const handleCancel = async () => {
    if (!state.apiKey || !predictionId) return;
    cancelledRef.current = true;
    try {
      await cancelPrediction({ apiKey: state.apiKey }, predictionId);
    } catch (e) {
      if (e instanceof ReplicateAuthError) forgetKey();
    }
    if (attempt) {
      updateAttempt(attempt.attemptId, { status: "error", errorMessage: "Cancelled by user." });
    }
    setCurrentJob(null);
    navigate("/");
  };

  if (poll.status === "failed") {
    return (
      <div className="max-w-md mx-auto px-6 py-24 flex flex-col items-center gap-4 text-center">
        <h1 className="text-xl font-semibold text-ink">Prediction failed</h1>
        <p className="text-ink-dim text-sm">{poll.error ?? "Replicate did not return a result."}</p>
        <a href="/" className="btn-primary">Try again</a>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-16 flex flex-col gap-6">
      <Step phase={phase} />

      <div className="h-2 rounded-full bg-bg-raised overflow-hidden">
        <div
          className="h-full bg-accent transition-[width] duration-500 ease-out"
          style={{ width: `${(fraction * 100).toFixed(1)}%` }}
        />
      </div>

      <ol className="flex flex-col gap-2 text-sm">
        <Row label="Uploaded" done={phase !== "upload"} elapsedMs={null} />
        <Row label="Submitted to Replicate" done={phase !== "upload" && phase !== "submitted"} elapsedMs={null} />
        <Row label="Booting model" done={phase === "inference" || phase === "done"} active={phase === "boot"} elapsedMs={phase === "boot" ? elapsedInPhaseMs : null} />
        <Row label="Predicting brain response" done={phase === "done"} active={phase === "inference"} elapsedMs={phase === "inference" ? elapsedInPhaseMs : null} />
      </ol>

      {phase === "boot" && (
        <div className="rounded-lg border border-border-subtle p-4 text-xs text-ink-muted leading-relaxed">
          {isColdStart
            ? "Replicate is starting a GPU machine and loading the TRIBE v2 model. The first prediction after idle takes ~60 seconds; subsequent runs are much faster."
            : "Starting up…"}
        </div>
      )}

      <button onClick={handleCancel} className="btn-ghost text-sm self-start">Cancel</button>
    </div>
  );
}

function Step({ phase }: { phase: Phase }) {
  const labels: Record<Phase, string> = {
    upload: "Step 1 of 4 — Uploading",
    submitted: "Step 2 of 4 — Queued",
    boot: "Step 2 of 4 — Booting model",
    inference: "Step 3 of 4 — Predicting brain response",
    done: "Step 4 of 4 — Done",
  };
  return <h1 className="text-lg font-semibold text-ink">{labels[phase]}</h1>;
}

function Row({
  label, done, active, elapsedMs,
}: {
  label: string; done: boolean; active?: boolean; elapsedMs: number | null;
}) {
  const icon = done ? "✓" : active ? "▶" : " ";
  const color = done ? "text-ink" : active ? "text-accent" : "text-ink-dim";
  return (
    <li className={`flex items-center justify-between ${color}`}>
      <span className="flex items-center gap-2">
        <span className="font-mono w-3">{icon}</span>
        {label}
      </span>
      <span className="font-mono text-xs text-ink-dim">
        {elapsedMs == null ? "" : formatElapsed(elapsedMs)}
      </span>
    </li>
  );
}
