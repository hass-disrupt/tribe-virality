const META: Record<string, { label: string; icon: string; desc: (s: number) => string }> = {
  reward: {
    label: "Reward",
    icon: "✦",
    desc: (s) =>
      s >= 70 ? "Strong reward signal — viewers are likely to feel satisfaction" :
      s >= 45 ? "Moderate reward signal" :
      "Low reward signal — consider adding a clear payoff or hook",
  },
  emotion: {
    label: "Emotion",
    icon: "◉",
    desc: (s) =>
      s >= 70 ? "High emotional arousal — content triggers feelings that drive sharing" :
      s >= 45 ? "Moderate emotional engagement" :
      "Low emotional resonance — consider evoking stronger feelings",
  },
  attention: {
    label: "Attention",
    icon: "▲",
    desc: (s) =>
      s >= 70 ? "High sensory capture — visuals and audio are grabbing the brain" :
      s >= 45 ? "Moderate attention capture" :
      "Low attention — try stronger visual contrast or audio hooks",
  },
  novelty: {
    label: "Novelty",
    icon: "◈",
    desc: (s) =>
      s >= 70 ? "High novelty — the brain detects something surprising and new" :
      s >= 45 ? "Some novelty detected" :
      "Low novelty — consider unexpected elements or creative cuts",
  },
  social_relevance: {
    label: "Social",
    icon: "⬡",
    desc: (s) =>
      s >= 70 ? "High social relevance — triggers self-referential and social cognition" :
      s >= 45 ? "Moderate social relevance" :
      "Low social signal — consider cultural references or relatable scenarios",
  },
};

const SUB_SCORE_COLOR: Record<string, string> = {
  reward: "#a78bfa",
  emotion: "#f472b6",
  attention: "#38bdf8",
  novelty: "#fb923c",
  social_relevance: "#4ade80",
};

interface SubScoreCardProps {
  name: string;
  value: number;
}

export function SubScoreCard({ name, value }: SubScoreCardProps) {
  const meta = META[name] ?? { label: name, icon: "·", desc: () => "" };
  const color = SUB_SCORE_COLOR[name] ?? "#a78bfa";
  const rounded = Math.round(value);

  return (
    <div className="card p-4 flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base" style={{ color }}>{meta.icon}</span>
          <span className="text-sm font-medium text-ink">{meta.label}</span>
        </div>
        <span className="font-mono text-sm font-semibold" style={{ color }}>{rounded}</span>
      </div>
      {/* Bar */}
      <div className="h-1.5 rounded-full bg-border-subtle overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${rounded}%`, background: color }}
        />
      </div>
      <p className="text-xs text-ink-dim leading-snug">{meta.desc(rounded)}</p>
    </div>
  );
}
