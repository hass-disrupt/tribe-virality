import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useAppState } from "../state/AppState";
import { ReplicateAuthError, ReplicateNetworkError, validateToken } from "../lib/replicate";

export function ApiKeyGate() {
  const { setApiKey } = useAppState();
  const [token, setToken] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const account = await validateToken(token);
      setApiKey(token, account);
    } catch (e) {
      if (e instanceof ReplicateAuthError) {
        setError("That token didn't work — double-check you copied the whole r8_… string.");
      } else if (e instanceof ReplicateNetworkError) {
        setError("Couldn't reach Replicate. Try again.");
      } else {
        setError("Something went wrong validating the token.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-6">
      <form onSubmit={handleSubmit} className="w-full max-w-[640px] card p-8 flex flex-col gap-5">
        <h1 className="text-2xl font-semibold text-ink">Tribe Virality</h1>
        <p className="text-ink-muted text-sm leading-relaxed">
          This is a research tool. To run a prediction we need your Replicate
          API token — you bring your own credits.
        </p>

        <div className="rounded-lg border border-border-subtle p-4 text-sm text-ink-muted leading-relaxed">
          <ol className="list-decimal pl-5 space-y-1">
            <li>Create a free Replicate account at <a className="underline" href="https://replicate.com" target="_blank" rel="noreferrer">replicate.com</a>.</li>
            <li>Add billing credits (predictions cost ~$0.05–0.20 each).</li>
            <li>Create an API token at <a className="underline" href="https://replicate.com/account/api-tokens" target="_blank" rel="noreferrer">replicate.com/account/api-tokens</a>.</li>
            <li>Paste it below.</li>
          </ol>
        </div>

        <label className="flex flex-col gap-2">
          <span className="text-sm text-ink">Replicate API token</span>
          <div className="relative">
            <input
              type={visible ? "text" : "password"}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="r8_…"
              autoComplete="off"
              spellCheck={false}
              className="w-full pr-10 px-3 py-2 rounded-lg bg-bg-raised border border-border-strong text-ink font-mono text-sm focus:outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={() => setVisible((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-ink-dim hover:text-ink"
              aria-label={visible ? "Hide token" : "Show token"}
            >
              {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </label>

        {error && <p className="text-bad text-sm">{error}</p>}

        <p className="text-xs text-ink-dim">
          🔒 Stored in memory only. Cleared when you refresh or close this tab.
          Never sent to any server we operate.
        </p>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={busy || token.trim().length === 0}
            className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy ? "Verifying token…" : "Continue"}
          </button>
        </div>
      </form>
    </div>
  );
}
