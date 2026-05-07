import { AlertTriangle, AlertCircle, CheckCircle2, Cpu } from "lucide-react";
import type { CapabilitiesResponse } from "../lib/api";

interface Props {
  capabilities: CapabilitiesResponse | null;
  loading: boolean;
}

const DISMISS_KEY = "capability-banner-dismissed";

export function CapabilityBanner({ capabilities, loading }: Props) {
  if (loading || !capabilities) return null;

  const { tier, active_backend, accelerator, accelerator_name, total_memory_gb, fallback_reason, warnings } =
    capabilities;

  // Green and no warnings -> short status chip showing what's running
  if (tier === "green" && active_backend === "local" && warnings.length === 0) {
    return (
      <div className="w-full max-w-3xl mx-auto px-4">
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <CheckCircle2 className="w-3.5 h-3.5 text-good" />
          <span>
            TRIBE v2 running locally on{" "}
            <span className="text-ink">{accelerator_name || accelerator.toUpperCase()}</span>
            {" · "}
            <span className="font-mono">{capabilities.active_dtype}</span>
            {" · "}
            <span>{total_memory_gb.toFixed(0)} GB</span>
          </span>
        </div>
      </div>
    );
  }

  // Yellow: dismissible warning
  if (tier === "yellow") {
    if (typeof window !== "undefined" && sessionStorage.getItem(DISMISS_KEY) === "yes") {
      return null;
    }
    return (
      <div className="w-full max-w-3xl mx-auto px-4">
        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-3 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-sm text-ink">
            <p className="font-medium text-yellow-300">Limited compute detected</p>
            {warnings.map((w, i) => (
              <p key={i} className="text-ink-muted text-xs mt-1">
                {w}
              </p>
            ))}
            <p className="text-ink-dim text-[11px] mt-2 flex items-center gap-2">
              <Cpu className="w-3 h-3" />
              <span>
                {accelerator_name || accelerator.toUpperCase()} · {total_memory_gb.toFixed(0)} GB ·{" "}
                running on <span className="font-mono">{active_backend}</span>
              </span>
            </p>
          </div>
          <button
            onClick={() => {
              sessionStorage.setItem(DISMISS_KEY, "yes");
              window.dispatchEvent(new Event("capability-banner-dismiss"));
            }}
            className="text-yellow-400 hover:text-yellow-300 text-xs px-2 py-1 rounded"
            aria-label="Dismiss"
          >
            Dismiss
          </button>
        </div>
      </div>
    );
  }

  // Red: non-dismissible (something is wrong; user must know)
  if (tier === "red") {
    return (
      <div className="w-full max-w-3xl mx-auto px-4">
        <div className="rounded-xl border border-bad/40 bg-bad/10 p-3 flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-bad mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-sm">
            <p className="font-medium text-bad">
              Local inference unavailable — running with mock backend
            </p>
            {fallback_reason && (
              <p className="text-ink-muted text-xs mt-1 leading-relaxed">{fallback_reason}</p>
            )}
            <p className="text-ink-dim text-[11px] mt-2 flex items-center gap-2">
              <Cpu className="w-3 h-3" />
              <span>
                {accelerator_name || accelerator.toUpperCase()} · {total_memory_gb.toFixed(0)} GB
              </span>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
