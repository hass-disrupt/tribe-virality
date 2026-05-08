import { useAppState } from "../state/AppState";

export function KeyChip() {
  const { state, forgetKey } = useAppState();
  if (!state.apiKey) return null;
  return (
    <div className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full bg-bg-raised border border-border-subtle">
      <span className="w-2 h-2 rounded-full bg-good" />
      <span className="text-ink font-mono">{state.apiKeyAccount?.username ?? "key"}</span>
      <span className="text-ink-dim">·</span>
      <button
        type="button"
        onClick={forgetKey}
        className="text-ink-dim hover:text-ink underline-offset-2 hover:underline"
      >
        forget key
      </button>
    </div>
  );
}
