import { usePlaybackSync } from "../hooks/usePlaybackSync";
import { api } from "../lib/api";
import { cn } from "../lib/cn";

interface VideoPairProps {
  attemptId: string;
  hasBrainVideo: boolean;
  onTimeUpdate?: (t: number) => void;
}

export function VideoPair({ attemptId, hasBrainVideo, onTimeUpdate }: VideoPairProps) {
  const { userRef, brainRef, onPlay, onPause, onSeeked, onTimeUpdate: syncTimeUpdate } = usePlaybackSync();

  const handleTimeUpdate = () => {
    syncTimeUpdate();
    if (onTimeUpdate && userRef.current) {
      onTimeUpdate(userRef.current.currentTime);
    }
  };

  return (
    <div className={cn(
      "grid gap-3",
      hasBrainVideo ? "grid-cols-2" : "grid-cols-1"
    )}>
      {/* User video */}
      <div className="relative rounded-xl overflow-hidden bg-bg-raised border border-border-subtle">
        <video
          ref={userRef}
          src={api.videoUrl(attemptId)}
          controls
          className="w-full aspect-video object-contain bg-black"
          onPlay={onPlay}
          onPause={onPause}
          onSeeked={onSeeked}
          onTimeUpdate={handleTimeUpdate}
        />
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded text-xs text-ink-dim bg-bg/70 backdrop-blur-sm">
          Your video
        </div>
      </div>

      {/* Brain activity video */}
      {hasBrainVideo && (
        <div className="relative rounded-xl overflow-hidden bg-bg-raised border border-border-subtle">
          <video
            ref={brainRef}
            src={api.brainVideoUrl(attemptId)}
            muted
            playsInline
            className="w-full aspect-video object-contain bg-black"
          />
          <div className="absolute top-2 left-2 px-2 py-0.5 rounded text-xs text-ink-dim bg-bg/70 backdrop-blur-sm">
            Brain activity
          </div>
          <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded text-xs text-ink-dim bg-bg/70 backdrop-blur-sm">
            Playing in sync
          </div>
        </div>
      )}
    </div>
  );
}
