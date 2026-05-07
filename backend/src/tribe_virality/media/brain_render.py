"""Render a synced brain-activity video alongside the user's input.

Produces an MP4 showing a stylized two-hemisphere cortical outline with
per-ROI-bucket glow intensity that tracks the input's sub-score curves
over time.

This implementation is deliberately lightweight — it uses matplotlib +
imageio (ffmpeg writer) so it runs without PyVista, without a GPU, and
without an offscreen display server. The layout is designed to look
aesthetic on a dark UI and to communicate the 5-bucket activation story
faithfully, while avoiding any pretense that it's a true 3D cortical render.
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any

import numpy as np

from ..config import settings
from ..scoring.constants import SUB_SCORE_NAMES
from ..scoring.pipeline import sub_score_curves


_SUB_SCORE_LABELS = {
    "reward": "Reward",
    "emotion": "Emotion",
    "attention": "Attention",
    "novelty": "Novelty",
    "social_relevance": "Social",
}

# Stylized 2D positions for each bucket on each hemisphere (normalized 0..1).
# Laid out on an ovoid "brain outline" silhouette.
# Tuned to read left->right (front->back) on each hemisphere panel.
_BUCKET_LH = {
    "reward":           (0.22, 0.62),
    "emotion":          (0.35, 0.72),
    "attention":        (0.55, 0.55),
    "novelty":          (0.72, 0.40),
    "social_relevance": (0.45, 0.35),
}
_BUCKET_RH = _BUCKET_LH  # mirror-symmetric; we flip X in the right panel


def _brain_outline_path() -> "tuple[np.ndarray, np.ndarray]":
    """Return (x, y) arrays tracing a stylized brain-hemisphere outline."""
    # Parametric blob: slightly flattened on the bottom, rounded on top.
    theta = np.linspace(0, 2 * np.pi, 200)
    r = 0.42 + 0.02 * np.sin(4 * theta) + 0.015 * np.cos(3 * theta)
    # Squish the bottom a bit to look brain-ish.
    x = 0.5 + r * np.cos(theta)
    y = 0.5 + r * np.sin(theta) * (0.9 if True else 1.0)
    # Gentle ventral flattening
    y = np.where(y < 0.5, 0.5 + (y - 0.5) * 0.85, y)
    return x, y


def _normalize_curve(curve: np.ndarray) -> np.ndarray:
    """Map a (T,) curve to [0, 1] using its min/max."""
    lo = float(curve.min())
    hi = float(curve.max())
    if hi - lo < 1e-8:
        return np.full_like(curve, 0.5, dtype=np.float64)
    return (curve - lo) / (hi - lo)


def _interp_at(times_source: np.ndarray, values: np.ndarray, t: float) -> float:
    """Linear interpolate `values` sampled at `times_source` at time t."""
    if t <= times_source[0]:
        return float(values[0])
    if t >= times_source[-1]:
        return float(values[-1])
    return float(np.interp(t, times_source, values))


async def render_brain_video(
    preds: np.ndarray,
    duration_s: float,
    out_path: Path,
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
) -> Path:
    """Render the brain-activity MP4. Returns the output path.

    Runs the matplotlib work in a thread; imageio uses ffmpeg under the hood.
    """
    width = width or settings.brain_render_width
    height = height or settings.brain_render_height
    fps = fps or settings.brain_render_fps

    # Compute per-bucket (T,) curves and normalize each to [0,1] for rendering.
    curves_raw = sub_score_curves(preds)
    curves_norm: dict[str, np.ndarray] = {
        name: _normalize_curve(curves_raw[name]) for name in SUB_SCORE_NAMES
    }
    t_source = np.linspace(0.0, duration_s, num=preds.shape[0], dtype=np.float64)

    def _work() -> Path:
        # Import heavy deps inside the thread.
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon
        from matplotlib.collections import PatchCollection
        import imageio.v2 as imageio

        out_path.parent.mkdir(parents=True, exist_ok=True)

        accent = (0.655, 0.545, 0.980)  # #a78bfa
        bg = (0.039, 0.039, 0.043)       # #0a0a0b
        outline_color = (0.16, 0.16, 0.19)

        x_outline, y_outline = _brain_outline_path()
        n_frames = max(2, int(round(duration_s * fps)))
        dpi = 100
        fig_w = width / dpi
        fig_h = height / dpi

        writer = imageio.get_writer(
            str(out_path),
            fps=fps,
            codec="libx264",
            quality=8,
            macro_block_size=1,
        )
        try:
            for f_idx in range(n_frames):
                t = duration_s * (f_idx / max(1, n_frames - 1))

                fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h), dpi=dpi,
                                         gridspec_kw={"wspace": 0.02})
                fig.patch.set_facecolor(bg)

                # Current activation per bucket at time t in [0,1].
                activations = {
                    name: _interp_at(t_source, curves_norm[name], t)
                    for name in SUB_SCORE_NAMES
                }

                for panel_idx, ax in enumerate(axes):
                    ax.set_facecolor(bg)
                    ax.set_xlim(0, 1)
                    ax.set_ylim(0, 1)
                    ax.set_aspect("equal")
                    ax.set_xticks([])
                    ax.set_yticks([])
                    for spine in ax.spines.values():
                        spine.set_visible(False)

                    # Hemisphere outline.
                    mirror = panel_idx == 1
                    xo = 1.0 - x_outline if mirror else x_outline
                    ax.fill(xo, y_outline, color=(0.08, 0.08, 0.10), alpha=1.0, zorder=1)
                    ax.plot(xo, y_outline, color=outline_color, linewidth=1.2, zorder=2)

                    # Draw activation "glow" discs per bucket.
                    for name in SUB_SCORE_NAMES:
                        bx, by = _BUCKET_LH[name]
                        if mirror:
                            bx = 1.0 - bx
                        activation = activations[name]  # 0..1
                        # Outer halo
                        for ring, alpha_scale in [(0.11, 0.18), (0.075, 0.32), (0.045, 0.55)]:
                            ax.scatter(
                                [bx], [by],
                                s=(ring * 1000) ** 2 / 80,
                                color=accent,
                                alpha=alpha_scale * (0.25 + 0.75 * activation),
                                zorder=3,
                                edgecolors="none",
                            )
                        # Core dot
                        ax.scatter(
                            [bx], [by],
                            s=55 + 120 * activation,
                            color=(1.0, 1.0, 1.0),
                            alpha=0.35 + 0.65 * activation,
                            zorder=4,
                            edgecolors="none",
                        )

                    # Hemisphere label
                    label = "L" if panel_idx == 0 else "R"
                    ax.text(0.04 if panel_idx == 0 else 0.96, 0.96, label,
                            color=(0.56, 0.56, 0.58), fontsize=9,
                            ha="left" if panel_idx == 0 else "right",
                            va="top", family="monospace",
                            transform=ax.transAxes)

                # Title strip: time + top bucket
                top_bucket = max(activations.items(), key=lambda kv: kv[1])[0]
                fig.text(
                    0.5, 0.04,
                    f"{t:0.1f}s  ·  peak: {_SUB_SCORE_LABELS[top_bucket]}",
                    color=(0.70, 0.70, 0.74), fontsize=9, ha="center", family="monospace",
                )

                # Capture frame as array.
                fig.canvas.draw()
                buf = np.asarray(fig.canvas.buffer_rgba())
                # Strip alpha for the MP4 writer.
                frame = buf[..., :3].copy()
                writer.append_data(frame)
                plt.close(fig)
        finally:
            writer.close()
        return out_path

    return await asyncio.to_thread(_work)
