import { useState } from "react";
import type { ReactNode } from "react";
import { ackDisclaimer } from "../lib/disclaimerAck";

interface DisclaimerProps {
  onAck: () => void;
  readOnly?: boolean;
}

export function Disclaimer({ onAck, readOnly = false }: DisclaimerProps) {
  const [checked, setChecked] = useState(false);

  const handleContinue = () => {
    ackDisclaimer();
    onAck();
  };

  return (
    <div className="min-h-screen bg-bg flex items-start sm:items-center justify-center p-4 sm:p-8">
      <div className="w-full max-w-[720px] card p-6 sm:p-8 flex flex-col gap-5">
        <h1 className="text-2xl font-semibold text-ink">Tribe Virality</h1>
        {!readOnly && (
          <p className="text-ink-muted text-sm">Before you continue, please read.</p>
        )}

        <Section title="About this tool">
          Tribe Virality is a research-oriented web app that uses Meta's
          TRIBE&nbsp;v2 brain-predictive foundation model to estimate how a
          generic viewer's brain might respond to a short video. It runs the
          model on Replicate using <strong>your</strong> Replicate API token
          and <strong>your</strong> Replicate credits.
        </Section>

        <Section title="About TRIBE v2">
          <ul className="list-disc pl-5 space-y-1">
            <li>Model: <code>facebook/tribev2</code> by Meta AI Research</li>
            <li>License: CC-BY-NC-4.0 (non-commercial use only)</li>
            <li>You may not use this tool, its outputs, or any derivative work for commercial purposes.</li>
          </ul>
        </Section>

        <Section title="Accuracy & limitations">
          <ul className="list-disc pl-5 space-y-1">
            <li>This is a <strong>research-grade approximation</strong>, not a clinical or scientific instrument.</li>
            <li>Scores are computed from cortical proxies of reward, emotion, attention, novelty, and social-cognition networks. Subcortical structures are not modeled.</li>
            <li>A "Virality Score" is a heuristic — there is no guarantee that real-world video performance correlates with it.</li>
            <li>Results are not medical, diagnostic, or psychological advice of any kind.</li>
          </ul>
        </Section>

        <Section title="Your data">
          <ul className="list-disc pl-5 space-y-1">
            <li>Your video is uploaded directly from your browser to Replicate. It does not pass through any server operated by the developer of this tool.</li>
            <li>Your Replicate API token is held in browser memory only and is cleared when you refresh or close this tab.</li>
            <li>No accounts, no telemetry, no analytics on your activity.</li>
          </ul>
        </Section>

        <Section title="Costs">
          <ul className="list-disc pl-5 space-y-1">
            <li>Each prediction is billed by Replicate to your account.</li>
            <li>Typical cost is approximately $0.05–$0.20 per run, but the developer makes no guarantees about price or availability.</li>
          </ul>
        </Section>

        <Section title="Liability">
          This tool is provided "AS IS", without warranty of any kind, express
          or implied. The developer (Prakhar Bhartiya) is not liable for any
          costs, damages, decisions, or consequences arising from your use of
          this tool, the TRIBE&nbsp;v2 model, or the predictions it produces.
          {!readOnly && " By continuing, you acknowledge that you understand and accept these terms."}
        </Section>

        {!readOnly && (
          <>
            <label className="flex items-start gap-3 text-sm text-ink select-none cursor-pointer mt-2">
              <input
                type="checkbox"
                checked={checked}
                onChange={(e) => setChecked(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                I have read and understood the above. I am using this tool for
                non-commercial research purposes only.
              </span>
            </label>
            <div className="flex justify-end">
              <button
                disabled={!checked}
                onClick={handleContinue}
                className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </>
        )}

        <div className="border-t border-border-subtle pt-4 text-xs text-ink-dim">
          Built on{" "}
          <a className="underline" href="https://huggingface.co/facebook/tribev2" target="_blank" rel="noreferrer">
            facebook/tribev2
          </a>
          {" "}· CC-BY-NC-4.0
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-ink uppercase tracking-wide">{title}</h2>
      <div className="text-sm text-ink-muted leading-relaxed">{children}</div>
    </div>
  );
}
