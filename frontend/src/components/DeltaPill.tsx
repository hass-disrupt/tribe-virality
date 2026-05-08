import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import { cn } from "../lib/cn";

interface DeltaPillProps {
  delta: number;
  label?: string;
}

export function DeltaPill({ delta, label }: DeltaPillProps) {
  const isPositive = delta > 0;
  const isNeutral = delta === 0;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-mono font-semibold",
        isNeutral ? "bg-border-strong text-ink-muted" :
        isPositive ? "bg-good/15 text-good" : "bg-bad/15 text-bad",
      )}
    >
      {isNeutral ? <Minus className="w-3 h-3" /> :
       isPositive ? <TrendingUp className="w-3 h-3" /> :
       <TrendingDown className="w-3 h-3" />}
      {isPositive ? "+" : ""}{delta}
      {label && <span className="ml-0.5 text-inherit opacity-60">{label}</span>}
    </span>
  );
}
