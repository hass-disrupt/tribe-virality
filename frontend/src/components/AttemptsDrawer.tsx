import { X, Clock, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Attempt } from "../types";
import { cn } from "../lib/cn";

interface AttemptsDrawerProps {
  attempts: Attempt[];
  currentAttemptId: string;
  onClose: () => void;
  onDelete: (id: string) => void;
}

function statusDot(status: Attempt["status"]) {
  if (status === "done") return "bg-good";
  if (status === "error") return "bg-bad";
  return "bg-accent animate-pulse";
}

export function AttemptsDrawer({
  attempts, currentAttemptId, onClose, onDelete,
}: AttemptsDrawerProps) {
  const navigate = useNavigate();

  return (
    <>
      <div
        className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside className="fixed right-0 top-0 bottom-0 z-40 w-80 bg-bg-card border-l border-border-subtle flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <span className="font-medium text-sm text-ink">Upload history</span>
          <button onClick={onClose} className="btn-ghost p-1.5 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-2">
          {attempts.length === 0 && (
            <p className="text-xs text-ink-dim text-center py-8">No uploads yet</p>
          )}
          {attempts.map((a) => {
            const isCurrent = a.attemptId === currentAttemptId;
            return (
              <button
                key={a.attemptId}
                onClick={() => { if (!isCurrent) navigate(`/results/${a.attemptId}`); onClose(); }}
                className={cn(
                  "w-full text-left rounded-xl p-3 flex items-start gap-3 transition-colors group",
                  isCurrent
                    ? "bg-accent/10 border border-accent/30"
                    : "hover:bg-bg-raised border border-transparent"
                )}
              >
                <div className="mt-1 flex-shrink-0">
                  <span className={cn("inline-block w-2 h-2 rounded-full", statusDot(a.status))} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink truncate">{a.label}</span>
                    {a.headlineScore !== null && (
                      <span className="font-mono text-xs font-semibold text-accent flex-shrink-0">
                        {a.headlineScore}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 mt-0.5 text-xs text-ink-dim">
                    <Clock className="w-3 h-3" />
                    {new Date(a.uploadedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    <span>·</span>
                    <span>{a.videoDurationS.toFixed(1)}s</span>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(a.attemptId); }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-bad/20 text-ink-dim hover:text-bad"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </button>
            );
          })}
        </div>
      </aside>
    </>
  );
}
