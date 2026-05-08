import { cn } from "../lib/cn";

interface ScoreRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function ScoreRing({ score, size = 180, strokeWidth = 8, className }: ScoreRingProps) {
  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;
  const progress = Math.min(1, Math.max(0, score / 100));
  const dashoffset = circumference * (1 - progress);

  const color =
    score >= 70 ? "#4ade80" :
    score >= 45 ? "#a78bfa" :
    "#f87171";

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="#1f1f24"
          strokeWidth={strokeWidth}
        />
        {/* Progress arc */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashoffset}
          style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
        />
      </svg>
      {/* Score text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono font-bold leading-none" style={{ fontSize: size * 0.26, color }}>
          {score}
        </span>
        <span className="text-ink-dim mt-1" style={{ fontSize: size * 0.085 }}>
          / 100
        </span>
      </div>
    </div>
  );
}
