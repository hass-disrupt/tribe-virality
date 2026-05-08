import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import type { TimelinePoint } from "../lib/api";

const COLORS: Record<string, string> = {
  reward: "#a78bfa",
  emotion: "#f472b6",
  attention: "#38bdf8",
  novelty: "#fb923c",
  social_relevance: "#4ade80",
};

const LABELS: Record<string, string> = {
  reward: "Reward",
  emotion: "Emotion",
  attention: "Attention",
  novelty: "Novelty",
  social_relevance: "Social",
};

const ALL_KEYS = Object.keys(COLORS);

interface TimelineChartProps {
  timeline: TimelinePoint[];
  playheadTime?: number;
}

export function TimelineChart({ timeline, playheadTime }: TimelineChartProps) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const toggleKey = (key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  return (
    <div className="card p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className="text-sm font-medium text-ink">Brain Activity Timeline</span>
        {/* Legend toggles */}
        <div className="flex flex-wrap gap-1.5">
          {ALL_KEYS.map((k) => (
            <button
              key={k}
              onClick={() => toggleKey(k)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all"
              style={{
                borderColor: hidden.has(k) ? "#27272a" : COLORS[k],
                color: hidden.has(k) ? "#71717a" : COLORS[k],
                background: hidden.has(k) ? "transparent" : `${COLORS[k]}18`,
              }}
            >
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: hidden.has(k) ? "#27272a" : COLORS[k] }}
              />
              {LABELS[k]}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={timeline} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            tickFormatter={(v) => `${Number(v).toFixed(1)}s`}
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "#141418",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#a1a1aa", marginBottom: 4 }}
            labelFormatter={(v) => `${Number(v).toFixed(2)}s`}
            itemStyle={{ color: "#f5f5f7" }}
          />
          {playheadTime !== undefined && (
            <ReferenceLine x={playheadTime} stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="4 2" />
          )}
          {ALL_KEYS.filter((k) => !hidden.has(k)).map((k) => (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              name={LABELS[k]}
              stroke={COLORS[k]}
              strokeWidth={1.8}
              dot={false}
              activeDot={{ r: 4, fill: COLORS[k] }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
