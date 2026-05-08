import { useState } from "react";

export function usePlaybackSync(): {
  playheadTime: number;
  setPlayheadTime: (t: number) => void;
} {
  const [playheadTime, setPlayheadTime] = useState(0);
  return { playheadTime, setPlayheadTime };
}
