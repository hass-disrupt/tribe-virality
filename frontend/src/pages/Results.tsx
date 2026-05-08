import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { History, Upload, AlertCircle } from "lucide-react";
import { useAppState } from "../state/AppState";
import { ScoreRing } from "../components/ScoreRing";
import { DeltaPill } from "../components/DeltaPill";
import { SubScoreCard } from "../components/SubScoreCard";
import { TimelineChart } from "../components/TimelineChart";
import { BrainFrameStrip } from "../components/BrainFrameStrip";
import { AttemptsDrawer } from "../components/AttemptsDrawer";
import { HeadViewer3D } from "../components/HeadViewer3D";
import { useVideoThumbnails } from "../hooks/useVideoThumbnails";
import { SUB_SCORE_KEYS, type Attempt, type TimelinePoint } from "../types";

function interpolateAtTime(timeline: TimelinePoint[], t: number): TimelinePoint | null {
  if (!timeline.length) return null;
  if (t <= timeline[0].t) return timeline[0];
  const last = timeline[timeline.length - 1];
  if (t >= last.t) return last;
  const idx = timeline.findIndex((p) => p.t >= t);
  if (idx <= 0) return timeline[0];
  const p0 = timeline[idx - 1];
  const p1 = timeline[idx];
  const a = (t - p0.t) / (p1.t - p0.t);
  const lerp = (x: number, y: number) => x + (y - x) * a;
  return {
    t,
    reward: lerp(p0.reward, p1.reward),
    emotion: lerp(p0.emotion, p1.emotion),
    attention: lerp(p0.attention, p1.attention),
    novelty: lerp(p0.novelty, p1.novelty),
    social_relevance: lerp(p0.social_relevance, p1.social_relevance),
  };
}

export default function Results() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();
  const { state, updateAttempt, removeAttempt } = useAppState();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [playheadTime, setPlayheadTime] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  const attempt = useMemo<Attempt | null>(
    () => state.attempts.find((a) => a.attemptId === attemptId) ?? null,
    [state.attempts, attemptId],
  );

  useEffect(() => {
    if (!attempt) navigate("/", { replace: true });
  }, [attempt, navigate]);

  const thumbnails = useVideoThumbnails({
    videoUrl: attempt?.videoBlobUrl ?? "",
    durationS: attempt?.videoDurationS ?? 0,
  });

  const sortedAttempts = useMemo(
    () => [...state.attempts].sort(
      (a, b) => new Date(a.uploadedAt).getTime() - new Date(b.uploadedAt).getTime(),
    ),
    [state.attempts],
  );
  const currentIndex = sortedAttempts.findIndex((a) => a.attemptId === attemptId);
  const prevAttempt = currentIndex > 0 ? sortedAttempts[currentIndex - 1] : null;
  const delta = (attempt?.headlineScore != null && prevAttempt?.headlineScore != null)
    ? attempt.headlineScore - prevAttempt.headlineScore
    : null;

  const handleTimeUpdate = () => {
    if (videoRef.current) setPlayheadTime(videoRef.current.currentTime);
  };

  const handleSeek = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      setPlayheadTime(t);
    }
  };

  if (!attempt) {
    return (
      <div className="max-w-md mx-auto px-6 py-24 flex flex-col items-center gap-4 text-center">
        <AlertCircle className="w-8 h-8 text-bad" />
        <p className="text-ink">That session ended.</p>
        <a href="/" className="btn-primary">Start a new prediction</a>
      </div>
    );
  }

  const liveScores = attempt.timeline ? interpolateAtTime(attempt.timeline, playheadTime) : null;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-ink font-medium">{attempt.label}</span>
          <span className="text-ink-dim">·</span>
          <span className="text-ink-dim">{attempt.videoDurationS.toFixed(1)}s</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setDrawerOpen(true)} className="btn-ghost text-sm gap-1.5">
            <History className="w-4 h-4" /> History
            {state.attempts.length > 0 && (
              <span className="ml-0.5 text-xs bg-accent/20 text-accent rounded-full px-1.5 py-0.5 font-mono">
                {state.attempts.length}
              </span>
            )}
          </button>
          <a href="/" className="btn-primary text-sm gap-1.5">
            <Upload className="w-4 h-4" /> New upload
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" style={{ height: "clamp(240px, 34vw, 420px)" }}>
        <div className="relative rounded-xl overflow-hidden bg-black border border-border-subtle h-full">
          <video
            ref={videoRef}
            src={attempt.videoBlobUrl}
            controls
            className="w-full h-full object-contain"
            onTimeUpdate={handleTimeUpdate}
          />
        </div>
        <div className="relative rounded-xl overflow-hidden bg-black border border-border-subtle h-full">
          <HeadViewer3D
            timeline={attempt.timeline ?? []}
            playheadTime={playheadTime}
            className="w-full h-full"
          />
        </div>
      </div>

      {attempt.brainFrames && attempt.brainFrames.length > 0 ? (
        <BrainFrameStrip
          brainFrames={attempt.brainFrames}
          thumbnails={thumbnails}
          timeline={attempt.timeline ?? []}
          totalDuration={attempt.videoDurationS}
          frameCount={attempt.frameCount}
          playheadTime={playheadTime}
          onSeek={handleSeek}
        />
      ) : (
        <BrainFrameCaptureGate
          attempt={attempt}
          onCapture={(frames) => updateAttempt(attempt.attemptId, { brainFrames: frames })}
        />
      )}

      {attempt.timeline && attempt.timeline.length > 0 && (
        <TimelineChart timeline={attempt.timeline} playheadTime={playheadTime} />
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {SUB_SCORE_KEYS.map((key) => (
          <SubScoreCard
            key={key}
            name={key}
            value={liveScores?.[key] ?? attempt.subScores?.[key] ?? 0}
          />
        ))}
      </div>

      <div className="card p-6 flex flex-col sm:flex-row items-center gap-6">
        <ScoreRing score={attempt.headlineScore ?? 0} size={140} />
        <div className="flex flex-col gap-2 text-center sm:text-left">
          <div className="flex items-center gap-3 justify-center sm:justify-start flex-wrap">
            <span className="text-xl font-semibold text-ink">Overall Virality Score</span>
            {delta != null && prevAttempt && (
              <DeltaPill delta={delta} label={`vs ${prevAttempt.label}`} />
            )}
          </div>
          <p className="text-sm text-ink-muted leading-relaxed max-w-lg">
            Predicted from cortical reward, emotion, attention, novelty, and
            social-relevance networks using Meta's TRIBE v2 brain model.
            Upload a new version of your video and compare scores to optimise.
          </p>
        </div>
      </div>

      {drawerOpen && (
        <AttemptsDrawer
          attempts={state.attempts}
          currentAttemptId={attemptId ?? ""}
          onClose={() => setDrawerOpen(false)}
          onDelete={(id) => {
            removeAttempt(id);
            if (id === attemptId) navigate("/");
          }}
        />
      )}
    </div>
  );
}

/**
 * Mounts a hidden HeadViewer3D, drives it through frame timestamps, snapshots
 * its WebGL canvas, and emits the data URL array via onCapture.
 */
function BrainFrameCaptureGate({
  attempt, onCapture,
}: {
  attempt: Attempt; onCapture: (frames: string[]) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [done, setDone] = useState(false);
  const [t, setT] = useState(0);

  useEffect(() => {
    if (!attempt.timeline || attempt.frameCount <= 0) return;
    const node = containerRef.current;
    if (!node) return;
    let cancelled = false;

    const capture = async () => {
      const frames: string[] = [];
      const total = attempt.frameCount;
      const dur = attempt.videoDurationS;
      // Wait one animation frame for HeadViewer3D's renderer to mount + load.
      await new Promise((r) => requestAnimationFrame(() => r(null)));
      // Give Three.js loaders a moment on first mount.
      await new Promise((r) => setTimeout(r, 800));
      for (let i = 0; i < total; i++) {
        if (cancelled) return;
        const tt = total === 1 ? 0 : (i * dur) / (total - 1);
        setT(tt);
        await new Promise((r) => requestAnimationFrame(() => r(null)));
        const canvas = node.querySelector("canvas") as HTMLCanvasElement | null;
        if (!canvas) break;
        frames.push(canvas.toDataURL("image/jpeg", 0.85));
      }
      if (!cancelled) {
        onCapture(frames);
        setDone(true);
      }
    };
    capture();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt.attemptId]);

  if (done) return null;

  return (
    <>
      <div className="card p-4 flex items-center gap-3 text-sm text-ink-dim">
        <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin shrink-0" />
        Rendering brain frames…
      </div>
      <div ref={containerRef} style={{ position: "absolute", left: -9999, top: -9999, width: 96, height: 130 }}>
        <HeadViewer3D
          timeline={attempt.timeline ?? []}
          playheadTime={t}
          className="w-full h-full"
        />
      </div>
    </>
  );
}
