import { useCallback, useRef } from "react";

/**
 * Returns refs for two video elements and an event handler to attach to
 * the primary video. Keeps the brain video in lockstep with the user video.
 */
export function usePlaybackSync() {
  const userRef = useRef<HTMLVideoElement>(null);
  const brainRef = useRef<HTMLVideoElement>(null);
  const syncingRef = useRef(false);

  const syncBrain = useCallback(() => {
    const user = userRef.current;
    const brain = brainRef.current;
    if (!user || !brain || syncingRef.current) return;
    syncingRef.current = true;

    if (Math.abs(brain.currentTime - user.currentTime) > 0.15) {
      brain.currentTime = user.currentTime;
    }
    if (user.paused && !brain.paused) brain.pause();
    else if (!user.paused && brain.paused) {
      brain.play().catch(() => undefined);
    }

    syncingRef.current = false;
  }, []);

  const onPlay = useCallback(() => {
    brainRef.current?.play().catch(() => undefined);
    syncBrain();
  }, [syncBrain]);

  const onPause = useCallback(() => {
    brainRef.current?.pause();
    syncBrain();
  }, [syncBrain]);

  const onSeeked = useCallback(() => {
    syncBrain();
  }, [syncBrain]);

  const onTimeUpdate = useCallback(() => {
    syncBrain();
  }, [syncBrain]);

  return { userRef, brainRef, onPlay, onPause, onSeeked, onTimeUpdate };
}
