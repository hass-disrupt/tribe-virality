import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { useJobPolling } from "../hooks/useJobPolling";

const PULSE_DOTS = 5;

export default function Processing() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { state, error } = useJobPolling(jobId ?? null);

  useEffect(() => {
    if (state?.status === "done" && state.attempt_id) {
      navigate(`/results/${state.attempt_id}`, { replace: true });
    }
  }, [state, navigate]);

  const progress = state?.progress ?? 0;
  const label = state?.stage_label ?? "Starting…";
  const isError = state?.status === "error" || !!error;

  return (
    <div className="max-w-lg mx-auto px-6 py-24 flex flex-col items-center gap-10">
      {/* Animated glyph */}
      {!isError && (
        <div className="relative w-24 h-24 flex items-center justify-center">
          {Array.from({ length: PULSE_DOTS }).map((_, i) => (
            <div
              key={i}
              className="absolute rounded-full border border-accent/40"
              style={{
                width: `${40 + i * 16}%`,
                height: `${40 + i * 16}%`,
                opacity: 0.6 - i * 0.1,
                animation: `ping ${1.6 + i * 0.3}s cubic-bezier(0,0,.2,1) infinite`,
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
          <div className="w-6 h-6 rounded-full bg-accent/80 shadow-glow" />
        </div>
      )}

      {isError && (
        <div className="w-16 h-16 rounded-full bg-bad/10 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-bad" />
        </div>
      )}

      {/* Stage label */}
      <div className="text-center flex flex-col gap-2">
        <p className="font-medium text-ink">
          {isError ? "Something went wrong" : label}
        </p>
        {isError && (
          <p className="text-bad text-sm">{state?.error_message ?? error}</p>
        )}
      </div>

      {/* Progress bar */}
      {!isError && (
        <div className="w-full bg-border-subtle rounded-full h-1.5 overflow-hidden">
          <div
            className="h-full rounded-full bg-accent transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {isError && (
        <a href="/" className="btn-primary text-sm">Try again</a>
      )}

      <style>{`
        @keyframes ping {
          0% { transform: scale(0.8); opacity: 0.6; }
          80%, 100% { transform: scale(1.2); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
