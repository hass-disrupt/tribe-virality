import { useEffect, useState } from "react";

interface Args {
  videoUrl: string;
  durationS: number;
  width?: number;
  height?: number;
}

export function useVideoThumbnails({ videoUrl, durationS, width = 96, height = 54 }: Args): string[] {
  const [out, setOut] = useState<string[]>([]);

  useEffect(() => {
    if (!videoUrl || durationS <= 0) return;
    let cancelled = false;
    const v = document.createElement("video");
    v.crossOrigin = "anonymous";
    v.muted = true;
    v.preload = "auto";
    v.src = videoUrl;

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const seconds = Math.max(1, Math.floor(durationS) + 1);
    const collected: string[] = [];

    async function captureAt(t: number): Promise<string> {
      return new Promise<string>((resolve) => {
        const onSeeked = () => {
          v.removeEventListener("seeked", onSeeked);
          ctx!.drawImage(v, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", 0.7));
        };
        v.addEventListener("seeked", onSeeked);
        v.currentTime = Math.min(t, durationS);
      });
    }

    v.addEventListener("loadedmetadata", async () => {
      for (let s = 0; s < seconds; s++) {
        if (cancelled) return;
        collected.push(await captureAt(s));
        if (cancelled) return;
        setOut([...collected]);
      }
    });

    return () => { cancelled = true; };
  }, [videoUrl, durationS, width, height]);

  return out;
}
