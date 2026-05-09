/**
 * BrainFrameStrip — frame-by-frame analysis panel.
 *
 * Layout (vertical rows, horizontally scrollable):
 *   Row 1 — "Video"   : per-second thumbnail data URLs (drawn client-side from <video>)
 *   Row 2 — "Signal"  : mini area chart of headline activation over time
 *   Row 3 — "Brain"   : data URLs captured from an offscreen Three.js render
 *
 * A playhead cursor moves with the video; clicking any column seeks the video.
 */

import { useRef, useMemo, useEffect } from "react";
import type { TimelinePoint } from "../types";

// Square video cell so the canvas-side letterboxing in useVideoThumbnails
// gives portrait, square, and landscape clips comparable visible area.
const THUMB_W = 96;
const THUMB_H = 96;
const SIGNAL_H = 32;
const BRAIN_H = 130;
const GAP = 4;
const LABEL_W = 56;

function SignalRow({
  timeline,
  frameCount,
  totalDuration,
  width,
}: {
  timeline: TimelinePoint[];
  frameCount: number;
  totalDuration: number;
  width: number;
}) {
  if (!timeline.length || frameCount <= 1) {
    return <div style={{ height: SIGNAL_H }} className="bg-surface rounded" />;
  }

  const pts = timeline.map((p) => {
    const avg = (p.reward + p.emotion + p.attention + p.novelty + p.social_relevance) / 5;
    return { t: p.t, v: avg };
  });

  const xScale = width / totalDuration;
  const polyline = pts
    .map((p) => `${p.t * xScale},${SIGNAL_H - 2 - ((p.v / 100) * (SIGNAL_H - 6))}`)
    .join(" ");
  const areaPath =
    `M0,${SIGNAL_H - 2} ` +
    pts.map((p) => `L${p.t * xScale},${SIGNAL_H - 2 - ((p.v / 100) * (SIGNAL_H - 6))}`).join(" ") +
    ` L${width},${SIGNAL_H - 2} Z`;

  return (
    <svg width={width} height={SIGNAL_H} style={{ display: "block" }}>
      <path d={areaPath} fill="rgba(167,139,250,0.18)" />
      <polyline points={polyline} fill="none" stroke="#a78bfa" strokeWidth={1.5} />
    </svg>
  );
}

interface BrainFrameStripProps {
  brainFrames: string[];          // data URLs, length === frameCount
  thumbnails: string[];           // data URLs, length === floor(totalDuration)+1
  timeline: TimelinePoint[];
  totalDuration: number;
  frameCount: number;
  playheadTime: number;
  onSeek?: (t: number) => void;
}

export function BrainFrameStrip({
  brainFrames,
  thumbnails,
  timeline,
  totalDuration,
  frameCount,
  playheadTime,
  onSeek,
}: BrainFrameStripProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const frameTimes = useMemo(() => {
    if (frameCount <= 0) return [];
    const step = frameCount === 1 ? 0 : totalDuration / (frameCount - 1);
    return Array.from({ length: frameCount }, (_, i) => Math.min(i * step, totalDuration));
  }, [frameCount, totalDuration]);

  const thumbSeconds = useMemo(
    () => Array.from({ length: Math.max(1, Math.floor(totalDuration) + 1) }, (_, i) => i),
    [totalDuration],
  );

  const totalW = thumbSeconds.length * (THUMB_W + GAP);
  const playheadX = totalDuration > 0 ? (playheadTime / totalDuration) * totalW : 0;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const target = playheadX - el.clientWidth / 2;
    el.scrollLeft = Math.max(0, target);
  }, [playheadX]);

  const handleClick = (e: React.MouseEvent) => {
    if (!onSeek || !scrollRef.current) return;
    const rect = scrollRef.current.getBoundingClientRect();
    const relX = e.clientX - rect.left + scrollRef.current.scrollLeft - LABEL_W;
    const t = Math.max(0, Math.min(totalDuration, (relX / totalW) * totalDuration));
    onSeek(t);
  };

  const rows = [
    { label: "Video", height: THUMB_H },
    { label: "Signal", height: SIGNAL_H },
    { label: "Brain", height: BRAIN_H },
  ];

  return (
    <div className="card p-0 overflow-hidden">
      <div className="flex">
        <div
          className="flex flex-col shrink-0 border-r border-border-subtle"
          style={{ width: LABEL_W }}
        >
          {rows.map((r) => (
            <div
              key={r.label}
              className="flex items-center justify-end pr-3 text-[10px] text-ink-dim font-mono uppercase tracking-wide"
              style={{ height: r.height + GAP + 2 }}
            >
              {r.label}
            </div>
          ))}
        </div>

        <div
          ref={scrollRef}
          className="overflow-x-auto flex-1 relative cursor-pointer select-none"
          onClick={handleClick}
          style={{ scrollbarWidth: "thin" }}
        >
          <div style={{ width: totalW, position: "relative" }}>
            {/* Row 1: Video thumbnails */}
            <div className="flex gap-1" style={{ paddingTop: 2 }}>
              {thumbSeconds.map((s) => {
                const src = thumbnails[s];
                return (
                  <div
                    key={s}
                    className="shrink-0 rounded overflow-hidden bg-surface border border-border-subtle"
                    style={{ width: THUMB_W, height: THUMB_H }}
                  >
                    {src && (
                      <img
                        src={src}
                        alt={`t=${s}s`}
                        className="w-full h-full object-contain"
                        loading="lazy"
                      />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Row 2: Signal waveform */}
            <div style={{ marginTop: GAP }}>
              <SignalRow
                timeline={timeline}
                frameCount={frameCount}
                totalDuration={totalDuration}
                width={totalW}
              />
            </div>

            {/* Row 3: Brain frames */}
            <div className="flex gap-1" style={{ marginTop: GAP }}>
              {frameTimes.map((ft, idx) => {
                const src = brainFrames[idx];
                return (
                  <div
                    key={idx}
                    className="shrink-0 rounded overflow-hidden bg-black border border-border-subtle relative"
                    style={{ width: THUMB_W, height: BRAIN_H, position: "relative" }}
                  >
                    {src && (
                      <img
                        src={src}
                        alt={`brain t=${ft.toFixed(0)}s`}
                        className="w-full h-full object-contain"
                        loading="lazy"
                      />
                    )}
                    <span className="absolute bottom-1 left-0 right-0 text-center text-[9px] text-ink-dim font-mono pointer-events-none">
                      t={ft.toFixed(0)}s
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Playhead cursor */}
            <div
              className="absolute top-0 bottom-0 pointer-events-none"
              style={{
                left: playheadX,
                width: 2,
                background: "rgba(167,139,250,0.85)",
                zIndex: 10,
                borderRadius: 1,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
