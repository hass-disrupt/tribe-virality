import { useCallback, useEffect, useState } from "react";
import { api, type AttemptSummary } from "../lib/api";

export function useAttempts() {
  const [attempts, setAttempts] = useState<AttemptSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listAttempts();
      setAttempts(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { attempts, loading, refresh };
}
