import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { History, Upload, AlertCircle } from "lucide-react";
import { api, type AttemptResult, type TimelinePoint } from "../lib/api";
import { ScoreRing } from "../components/ScoreRing";
import { DeltaPill } from "../components/DeltaPill";
import { SubScoreCard } from "../components/SubScoreCard";
import { TimelineChart } from "../components/TimelineChart";
import { BrainFrameStrip } from "../components/BrainFrameStrip";
import { AttemptsDrawer } from "../components/AttemptsDrawer";
import { HeadViewer3D } from "../components/HeadViewer3D";
import { useAttempts } from "../hooks/useAttempts";

const SUB_SCORE_KEYS = [
  "reward",
  "emotion",
  "attention",
  "novelty",
  "social_relevance",
] as const;

function interpolateAtTime(
  timeline: TimelinePoint[],
  t: number,
): Record<string, number> {
  if (!timeline.length) return {};
  if (t <= timeline[0].t) return timeline[0] as unknown as Record<string, number>;
  const last = timeline[timeline.length - 1];
  if (t >= last.t) return last as unknown as Record<string, number>;
  const idx = timeline.findIndex((p) => p.t >= t);
  if (idx <= 0) return timeline[0] as unknown as Record<string, number>;
  const p0 = timeline[idx - 1];
  const p1 = timeline[idx];
  const a = (t - p0.t) / (p1.t - p0.t);
  const lerp = (x: number, y: number) => x + (y - x) * a;
  return {
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
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [playheadTime, setPlayheadTime] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const { attempts, refresh } = useAttempts();

  useEffect(() => {
    if (!attemptId) return;
    api
      .getAttempt(attemptId)
      .then(setResult)
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)));
  }, [attemptId]);

  // Poll for brain frames becoming available (rendered asynchronously after job done)
  useEffect(() => {
    if (!attemptId) return;
    if (result?.brain_frame_count && result.brain_frame_count > 0) return;
    if (!result || result.status !== "done") return;
    const id = setInterval(() => {
      api.getAttempt(attemptId).then((r) => {
        setResult(r);
        if (r.brain_frame_count > 0) clearInterval(id);
      }).catch(() => clearInterval(id));
    }, 2500);
    return () => clearInterval(id);
  }, [attemptId, result?.brain_frame_count, result?.status]);

  const handleTimeUpdate = () => {
    if (videoRef.current) setPlayheadTime(videoRef.current.currentTime);
  };

  const handleSeek = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      setPlayheadTime(t);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteAttempt(id);
    await refresh();
    if (id === attemptId) navigate("/");
  };

  const sortedAttempts = [...attempts].sort(
    (a, b) => new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime(),
  );
  const currentIndex = sortedAttempts.findIndex((a) => a.attempt_id === attemptId);
  const prevAttempt = currentIndex > 0 ? sortedAttempts[currentIndex - 1] : null;
  const delta =
    result?.headline_score != null && prevAttempt?.headline_score != null
      ? result.headline_score - prevAttempt.headline_score
      : null;

  const liveScores =
    result?.timeline && result.timeline.length > 0
      ? interpolateAtTime(result.timeline, playheadTime)
      : null;

  if (loadError) {
    return (
      <div className="max-w-lg mx-auto px-6 py-24 flex flex-col items-center gap-6 text-center">
        <AlertCircle className="w-10 h-10 text-bad" />
        <p className="text-ink font-medium">Failed to load results</p>
        <p className="text-ink-dim text-sm">{loadError}</p>
        <a href="/" className="btn-primary">Upload a video</a>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="w-8 h-8 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-5">

      {/* ── Action bar ──────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-ink font-medium">{result.label}</span>
          <span className="text-ink-dim">·</span>
          <span className="text-ink-dim">{result.video_duration_s.toFixed(1)}s</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setDrawerOpen(true)} className="btn-ghost text-sm gap-1.5">
            <History className="w-4 h-4" />
            History
            {attempts.length > 0 && (
              <span className="ml-0.5 text-xs bg-accent/20 text-accent rounded-full px-1.5 py-0.5 font-mono">
                {attempts.length}
              </span>
            )}
          </button>
          <a href="/" className="btn-primary text-sm gap-1.5">
            <Upload className="w-4 h-4" />
            New upload
          </a>
        </div>
      </div>

      {/* ── Row 1: Video player + 3D head viewer (side-by-side) ─ */}
      <div
        className="grid grid-cols-1 md:grid-cols-2 gap-4"
        style={{ height: "clamp(240px, 34vw, 420px)" }}
      >
        <div className="relative rounded-xl overflow-hidden bg-black border border-border-subtle h-full">
          <video
            ref={videoRef}
            src={api.videoUrl(result.attempt_id)}
            controls
            className="w-full h-full object-contain"
            onTimeUpdate={handleTimeUpdate}
          />
        </div>
        <div className="relative rounded-xl overflow-hidden bg-black border border-border-subtle h-full">
          <HeadViewer3D
            timeline={result.timeline ?? []}
            playheadTime={playheadTime}
            className="w-full h-full"
          />
        </div>
      </div>

      {/* ── Row 2: Brain Frame Strip ─────────────────────────── */}
      {result.brain_frame_count > 0 ? (
        <BrainFrameStrip
          attemptId={result.attempt_id}
          timeline={result.timeline ?? []}
          totalDuration={result.video_duration_s}
          frameCount={result.brain_frame_count}
          playheadTime={playheadTime}
          onSeek={handleSeek}
        />
      ) : (
        /* Fallback while frames are still rendering or unavailable */
        result.timeline && result.timeline.length > 0 && (
          <div className="card p-4 flex items-center gap-3 text-sm text-ink-dim">
            <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin shrink-0" />
            Brain frames rendering…
          </div>
        )
      )}

      {/* ── Row 3: Brain Activity Timeline ──────────────────── */}
      {result.timeline && result.timeline.length > 0 && (
        <TimelineChart timeline={result.timeline} playheadTime={playheadTime} />
      )}

      {/* ── Row 4: Live Sub-scores ──────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {SUB_SCORE_KEYS.map((key) => (
          <SubScoreCard
            key={key}
            name={key}
            value={liveScores?.[key] ?? result.sub_scores?.[key] ?? 0}
          />
        ))}
      </div>

      {/* ── Row 5: Overall Virality Score ───────────────────── */}
      <div className="card p-6 flex flex-col sm:flex-row items-center gap-6">
        <ScoreRing score={result.headline_score ?? 0} size={140} />
        <div className="flex flex-col gap-2 text-center sm:text-left">
          <div className="flex items-center gap-3 justify-center sm:justify-start flex-wrap">
            <span className="text-xl font-semibold text-ink">Overall Virality Score</span>
            {delta !== null && (
              <DeltaPill delta={delta} label={`vs ${prevAttempt?.label}`} />
            )}
          </div>
          <p className="text-sm text-ink-muted leading-relaxed max-w-lg">
            Predicted from cortical reward, emotion, attention, novelty, and
            social-relevance networks using Meta's TRIBE v2 brain model.
            Upload a new version of your video and compare scores to optimise for virality.
          </p>
        </div>
      </div>

      {/* ── Attempts drawer ─────────────────────────────────── */}
      {drawerOpen && (
        <AttemptsDrawer
          attempts={attempts}
          currentAttemptId={attemptId ?? ""}
          onClose={() => setDrawerOpen(false)}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}
