import type { TimelinePoint } from "../../types";

export type ZoneKey =
  | "reward"
  | "emotion"
  | "attention"
  | "novelty"
  | "social_relevance";

export type SubMap = Record<ZoneKey, number>;

/**
 * Vibrant 5-stop colormap on-brand with the app's #a78bfa purple accent.
 * Ramps deep purple → violet → magenta → orange → yellow as hotness rises.
 */
function hotRGB(t: number): [number, number, number] {
  // Stops chosen so adjacent transitions stay perceptually smooth and the
  // mid-range (0.4–0.7, where most real activations land) is the most
  // saturated. Each entry is [stop_position, [r, g, b]] in 0..1.
  const stops: ReadonlyArray<readonly [number, readonly [number, number, number]]> = [
    [0.00, [0.25, 0.10, 0.65]],  // deep indigo-purple
    [0.30, [0.65, 0.25, 0.95]],  // bright violet
    [0.55, [1.00, 0.30, 0.65]],  // hot magenta
    [0.80, [1.00, 0.55, 0.15]],  // saturated orange
    [1.00, [1.00, 1.00, 0.40]],  // bright yellow
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (t <= t1) {
      const a = (t - t0) / (t1 - t0);
      return [
        c0[0] + (c1[0] - c0[0]) * a,
        c0[1] + (c1[1] - c0[1]) * a,
        c0[2] + (c1[2] - c0[2]) * a,
      ];
    }
  }
  const last = stops[stops.length - 1][1];
  return [last[0], last[1], last[2]];
}

export const BRAIN_BASE_COLOR: [number, number, number] = [0.94, 0.93, 0.91];

/**
 * Map a [0,1] localized hotness to RGB. 0 = base cortical white,
 * 1 = peak yellow at the active spot's centroid. The blend exponent
 * controls how aggressively color appears at low hotness — 0.35 gives
 * visible tint even when activations are mild, which matches the real
 * TRIBE output range better than the old 0.6.
 */
export function hotnessToRGB(h: number): [number, number, number] {
  const t = Math.max(0, Math.min(1, h));
  if (t <= 0) return BRAIN_BASE_COLOR;
  const blend = Math.pow(t, 0.35);
  const [hr, hg, hb] = hotRGB(t);
  return [
    BRAIN_BASE_COLOR[0] + (hr - BRAIN_BASE_COLOR[0]) * blend,
    BRAIN_BASE_COLOR[1] + (hg - BRAIN_BASE_COLOR[1]) * blend,
    BRAIN_BASE_COLOR[2] + (hb - BRAIN_BASE_COLOR[2]) * blend,
  ];
}

/** Legacy direct mapping kept for the activity legend gradient calibration. */
export function activationToRGB(act: number): [number, number, number] {
  return hotnessToRGB(Math.max(0, (act - 70) / 30));
}

/**
 * Classify a vertex (unit-sphere coords relative to its hemisphere center)
 * into one of the five sub-score ROI zones.
 *
 * Coordinate conventions:
 *   +Y = superior   −Y = inferior
 *   +Z = anterior   −Z = posterior
 *   ±X = lateral
 */
export function getZone(nx: number, ny: number, nz: number): ZoneKey {
  if (nz > 0.30 && ny > -0.15) return "reward";
  if (nz < -0.28 && ny > 0.05) return "attention";
  if (Math.abs(nx) > 0.48 && ny < 0.25) return "emotion";
  if (ny < -0.42) return "novelty";
  return "social_relevance";
}

/** Linearly interpolate the 5 sub-scores at time `t` from a sorted timeline. */
export function interpolateScores(
  timeline: TimelinePoint[],
  t: number,
): SubMap {
  const fallback: SubMap = {
    reward: 50,
    emotion: 50,
    attention: 50,
    novelty: 50,
    social_relevance: 50,
  };
  if (!timeline.length) return fallback;
  if (t <= timeline[0].t) return timeline[0] as unknown as SubMap;
  const last = timeline[timeline.length - 1];
  if (t >= last.t) return last as unknown as SubMap;

  const idx = timeline.findIndex((p) => p.t >= t);
  if (idx <= 0) return timeline[0] as unknown as SubMap;
  const p0 = timeline[idx - 1];
  const p1 = timeline[idx];
  const a = (t - p0.t) / (p1.t - p0.t);
  const lerp = (x: number, y: number) => x + (y - x) * a;
  return {
    reward: lerp(p0.reward, p1.reward),
    emotion: lerp(p0.emotion, p1.emotion),
    attention: lerp(p0.attention, p1.attention),
    novelty: lerp(p0.novelty, p1.novelty),
    social_relevance: lerp(p0.social_relevance, p1.social_relevance),
  };
}

/**
 * Approximate ROI center direction (unit vector) per hemisphere. The lateral
 * "emotion" zone naturally lives on whichever side of the midline the vertex
 * is on, so we encode it as a per-side sign at the call site.
 *
 * Coords: +X lateral, +Y superior, +Z anterior.
 */
export const ZONE_CENTERS: Record<ZoneKey, [number, number, number]> = {
  reward:           [ 0.10,  0.10,  0.92], // frontal pole
  attention:        [ 0.05,  0.55, -0.78], // parietal/occipital
  emotion:          [ 0.92, -0.05,  0.05], // temporal/insular (sign flips per hemi)
  novelty:          [ 0.10, -0.78, -0.10], // inferior parahippocampal
  social_relevance: [ 0.02,  0.55,  0.10], // medial superior
};

/**
 * Compute, for a unit-normalized vertex direction, an "in-zone" weight in
 * [0,1] that peaks at the zone centroid and falls off with cosine distance.
 * `side` is +1 or -1 — used to mirror the lateral emotion centroid for the
 * correct hemisphere.
 */
export function zoneStrength(
  zone: ZoneKey,
  nx: number,
  ny: number,
  nz: number,
  side: number,
): number {
  const c = ZONE_CENTERS[zone];
  const cx = zone === "emotion" ? c[0] * side : c[0];
  const len = Math.hypot(nx, ny, nz) || 1;
  const dx = nx / len;
  const dy = ny / len;
  const dz = nz / len;
  const cl = Math.hypot(cx, c[1], c[2]) || 1;
  const dot = (dx * cx + dy * c[1] + dz * c[2]) / cl;
  // Tunes the spatial size of each ROI. Lower exponent = wider, glowier
  // hot patch. 1.8 gives readable footprints without zones bleeding into
  // each other.
  return Math.pow(Math.max(0, dot), 1.8);
}

export const ZONE_LABELS: Record<ZoneKey, string> = {
  reward: "Reward",
  emotion: "Emotion",
  attention: "Attention",
  novelty: "Novelty",
  social_relevance: "Social",
};

export const ZONE_REGIONS: Record<ZoneKey, string> = {
  reward: "Frontal / prefrontal",
  emotion: "Lateral / temporal",
  attention: "Parietal / occipital",
  novelty: "Inferior / parahippocampal",
  social_relevance: "Medial / mPFC, TPJ",
};
