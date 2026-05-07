import { useEffect, useState } from "react";
import { api, type CapabilitiesResponse } from "../lib/api";

interface UseCapabilitiesResult {
  data: CapabilitiesResponse | null;
  loading: boolean;
  error: string | null;
}

export function useCapabilities(): UseCapabilitiesResult {
  const [data, setData] = useState<CapabilitiesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .capabilities()
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to fetch capabilities");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error };
}
