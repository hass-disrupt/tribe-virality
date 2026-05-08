import { useEffect, useRef, useState } from "react";
import { api, type JobStatusResponse } from "../lib/api";

const POLL_INTERVAL_MS = 1500;

export function useJobPolling(jobId: string | null) {
  const [state, setState] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!jobId) return;
    stoppedRef.current = false;

    async function poll() {
      if (stoppedRef.current) return;
      try {
        const data = await api.getJob(jobId!);
        setState(data);
        if (data.status === "done" || data.status === "error") {
          stoppedRef.current = true;
          return;
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
      if (!stoppedRef.current) {
        timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [jobId]);

  return { state, error };
}
