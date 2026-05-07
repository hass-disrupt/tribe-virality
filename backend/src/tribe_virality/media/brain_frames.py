"""Render cortical surface brain frames as JPEG images.

Primary renderer: nilearn + actual fsaverage5 cortical mesh (inflated surface,
sulcal depth background, hot colormap) — matches the TRIBE v2 demo visual style.

Fallback renderer: procedural icosphere with multi-scale gyrification
(used only when nilearn/nibabel are unavailable).

Each frame is one JPEG rendered at ~240×240 px showing the LEFT lateral
hemisphere with per-zone activation from the TRIBE fMRI predictions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_ZONE_KEYS = ("reward", "emotion", "attention", "novelty", "social_relevance")
_BG = (0.06, 0.06, 0.07)
_ROI_MAP: dict | None = None
_FS_MESH: object | None = None   # nilearn fsaverage5 dict (lazy)
_NILEARN_OK: bool | None = None  # tri-state: None=untested, True/False


# ── ROI mapping ────────────────────────────────────────────────────────────

def _get_roi_map() -> dict:
    global _ROI_MAP
    if _ROI_MAP is None:
        p = Path(__file__).parent.parent / "data" / "roi_mapping.json"
        with open(p) as f:
            _ROI_MAP = json.load(f)
    return _ROI_MAP


def _activation_to_stat_map(activation: dict[str, float]) -> np.ndarray:
    """Build a (10242,) per-vertex activation array for the left hemisphere."""
    stat_map = np.zeros(10242, dtype=np.float32)
    roi = _get_roi_map()
    for zone, act in activation.items():
        if zone not in roi["buckets"]:
            continue
        for start, end in roi["buckets"][zone]["vertex_ranges"]:
            if start < 10242:
                stat_map[start : min(end, 10242)] = float(act)
    return stat_map


# ══════════════════════════════════════════════════════════════════════════
# PRIMARY RENDERER — nilearn + fsaverage5
# ══════════════════════════════════════════════════════════════════════════

def _check_nilearn() -> bool:
    global _NILEARN_OK
    if _NILEARN_OK is None:
        try:
            import nibabel  # noqa: F401
            import nilearn  # noqa: F401
            _NILEARN_OK = True
        except ImportError:
            _NILEARN_OK = False
    return _NILEARN_OK


def _get_fs_mesh():
    global _FS_MESH
    if _FS_MESH is None:
        from nilearn.datasets import fetch_surf_fsaverage
        _FS_MESH = fetch_surf_fsaverage("fsaverage5")
    return _FS_MESH


def _render_nilearn(
    activation: dict[str, float],
    frame_time: float,
    out_path: Path,
    size_px: int = 240,
) -> None:
    """Render using nilearn + actual fsaverage5 inflated surface."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from nilearn.plotting import plot_surf_stat_map

    fs = _get_fs_mesh()
    stat_map = _activation_to_stat_map(activation)

    dpi = 100
    fig_sz = size_px / dpi
    fig = plt.figure(figsize=(fig_sz, fig_sz), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")

    plot_surf_stat_map(
        surf_mesh=fs["infl_left"],
        stat_map=stat_map,
        bg_map=fs["sulc_left"],
        hemi="left",
        view="lateral",
        cmap="hot",
        vmin=0,
        vmax=100,
        threshold=10,       # values < 10 shown as background gray
        colorbar=False,
        bg_on_data=True,    # blend sulcal texture into activation colors
        axes=ax,
    )

    # Zoom in close — matches Meta demo style
    ax.set_box_aspect(None, zoom=1.4)

    # Dark background matching app theme
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    # Timestamp label
    ax.text2D(
        0.5, 0.03,
        f"t={frame_time:.0f}s",
        color=(0.55, 0.55, 0.60),
        fontsize=7,
        ha="center",
        transform=ax.transAxes,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        str(out_path),
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.02,
        facecolor=fig.get_facecolor(),
        format="jpeg",
        pil_kwargs={"quality": 88},
    )
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════
# FALLBACK RENDERER — procedural icosphere
# ══════════════════════════════════════════════════════════════════════════

import math

RADIUS = 52.0
_BASE_COLOR = np.array([0.82, 0.79, 0.75])
_PHI = (1 + math.sqrt(5)) / 2

_BASE_VERTS = np.array([
    [-1, _PHI, 0], [1, _PHI, 0], [-1, -_PHI, 0], [1, -_PHI, 0],
    [0, -1, _PHI], [0, 1, _PHI], [0, -1, -_PHI], [0, 1, -_PHI],
    [_PHI, 0, -1], [_PHI, 0, 1], [-_PHI, 0, -1], [-_PHI, 0, 1],
], dtype=np.float64)
_BASE_VERTS /= np.linalg.norm(_BASE_VERTS[0])

_BASE_FACES = np.array([
    [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
    [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
    [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
    [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1],
], dtype=np.int32)

_FB_MESH: tuple | None = None


def _subdivide(verts: list, faces: np.ndarray) -> tuple[list, np.ndarray]:
    midpoints: dict[tuple, int] = {}
    new_faces: list[list[int]] = []
    v = list(verts)

    def mid(i: int, j: int) -> int:
        key = (min(i, j), max(i, j))
        if key not in midpoints:
            m = (v[i] + v[j]) / 2.0
            m /= np.linalg.norm(m)
            midpoints[key] = len(v)
            v.append(m)
        return midpoints[key]

    for a, b, c in faces:
        ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
        new_faces += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
    return v, np.array(new_faces, dtype=np.int32)


def _build_fb_mesh() -> tuple:
    global _FB_MESH
    if _FB_MESH is None:
        v = list(_BASE_VERTS)
        f = _BASE_FACES.copy()
        for _ in range(4):
            v, f = _subdivide(v, f)
        uv = np.array(v, dtype=np.float64)

        # Gyrification
        x, y, z = uv[:, 0], uv[:, 1], uv[:, 2]
        theta = np.arccos(np.clip(y, -1, 1))
        phi = np.arctan2(z, x)
        bump = (
            6.0 * np.sin(8 * theta) * np.cos(5 * phi) +
            4.0 * np.sin(13 * theta + 0.9) * np.cos(9 * phi - 0.6) +
            2.8 * np.sin(5 * theta) * np.cos(16 * phi + 1.3) +
            1.8 * np.sin(19 * theta + 2.2) * np.cos(6 * phi + 0.4) +
            1.2 * np.sin(23 * theta + 1.5) * np.cos(12 * phi + 0.8)
        )
        r = RADIUS + bump
        st = np.sin(theta)
        verts = np.column_stack([r * st * np.cos(phi), r * np.cos(theta), r * st * np.sin(phi)])

        # Zone assignment
        zones = np.full(len(uv), 4, dtype=np.int8)
        zones[uv[:, 1] < -0.42] = 3
        zones[(np.abs(uv[:, 0]) > 0.48) & (uv[:, 1] < 0.25)] = 2
        zones[(uv[:, 2] < -0.28) & (uv[:, 1] > 0.05)] = 1
        zones[(uv[:, 2] > 0.30) & (uv[:, 1] > -0.15)] = 0

        # Face normals
        v0, v1, v2 = verts[f[:, 0]], verts[f[:, 1]], verts[f[:, 2]]
        n = np.cross(v1 - v0, v2 - v0)
        nrm = np.linalg.norm(n, axis=1, keepdims=True)
        nrm = np.where(nrm < 1e-12, 1e-12, nrm)
        normals = n / nrm

        _FB_MESH = (verts, f, zones, normals)
    return _FB_MESH


def _render_fallback(
    activation: dict[str, float],
    frame_time: float,
    out_path: Path,
    size_px: int = 220,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    verts, faces, zones, normals = _build_fb_mesh()
    v_act = np.array([activation.get(_ZONE_KEYS[int(z)], 50.0) for z in zones], dtype=np.float32)
    f_act = v_act[faces].mean(axis=1)

    # Hot colormap
    t = np.clip(f_act / 100.0, 0.0, 1.0)
    thr = 0.18
    colors = np.tile(_BASE_COLOR, (len(faces), 1)).copy()
    above = t > thr
    if above.any():
        nt = np.where(above, (t - thr) / (1.0 - thr), 0.0)
        blend = np.where(above, nt ** 0.65, 0.0)[:, np.newaxis]
        hot = np.column_stack([np.minimum(1, nt * 3),
                               np.minimum(1, np.maximum(0, nt * 3 - 1)),
                               np.minimum(1, np.maximum(0, nt * 3 - 2))])
        colors = colors * (1 - blend) + hot * blend

    # Back-face cull + lighting (left lateral view)
    cam = np.array([-0.985, 0.174, 0.0])
    front = normals @ cam > 0.0
    f_vis, n_vis, c_vis = faces[front], normals[front], colors[front]
    light = np.array([-0.5, 0.7, 0.5])
    light /= np.linalg.norm(light)
    diffuse = np.clip(n_vis @ light, 0, 1)
    c_lit = np.clip(c_vis * (0.38 + 0.62 * diffuse[:, np.newaxis]), 0, 1)

    # Remap: brain Y→mpl Z
    rv = verts[:, [0, 2, 1]]
    dpi = 100
    fig_sz = size_px / dpi
    fig = plt.figure(figsize=(fig_sz, fig_sz), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor(_BG)
    fig.patch.set_facecolor(_BG)
    ax.add_collection3d(Poly3DCollection(rv[f_vis], facecolors=c_lit, edgecolors="none",
                                         linewidths=0, zsort="average"))
    R = RADIUS + 14
    ax.set_xlim(-R, R); ax.set_ylim(-R, R); ax.set_zlim(-R, R)
    ax.view_init(elev=10, azim=180)
    ax.set_axis_off(); ax.grid(False)
    ax.text2D(0.5, 0.03, f"t={frame_time:.0f}s", color=(0.55, 0.55, 0.60),
              fontsize=7, ha="center", transform=ax.transAxes)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=dpi, bbox_inches="tight", pad_inches=0.02,
                facecolor=fig.get_facecolor(), format="jpeg", pil_kwargs={"quality": 85})
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════
# Dispatcher
# ══════════════════════════════════════════════════════════════════════════

def _render_one(activation: dict[str, float], frame_time: float, out_path: Path) -> None:
    if _check_nilearn():
        try:
            _render_nilearn(activation, frame_time, out_path)
            return
        except Exception as e:
            log.warning("nilearn render failed (%s), falling back to icosphere", e)
    _render_fallback(activation, frame_time, out_path)


# ══════════════════════════════════════════════════════════════════════════
# Public async entry point
# ══════════════════════════════════════════════════════════════════════════

async def render_brain_frames(
    timeline: list[dict],
    out_dir: Path,
    max_frames: int = 30,
) -> int:
    """Render one JPEG per second of video (capped at max_frames).

    Parameters
    ----------
    timeline : list of dicts with keys 't', 'reward', 'emotion', etc.
    out_dir  : directory for frame_000.jpg, frame_001.jpg, …
    max_frames : upper bound on rendered frames

    Returns
    -------
    Number of frames written.
    """
    if not timeline:
        return 0

    total_duration = timeline[-1]["t"]
    step = max(1.0, total_duration / max_frames)
    frame_times: list[float] = []
    t = 0.0
    while t <= total_duration + 0.01:
        frame_times.append(min(t, total_duration))
        t += step
    frame_times = frame_times[:max_frames]

    def _lerp(target_t: float) -> dict[str, float]:
        if target_t <= timeline[0]["t"]:
            return {k: timeline[0][k] for k in _ZONE_KEYS}
        last = timeline[-1]
        if target_t >= last["t"]:
            return {k: last[k] for k in _ZONE_KEYS}
        idx = next(i for i, p in enumerate(timeline) if p["t"] >= target_t)
        p0, p1 = timeline[idx - 1], timeline[idx]
        a = (target_t - p0["t"]) / (p1["t"] - p0["t"])
        return {k: p0[k] + (p1[k] - p0[k]) * a for k in _ZONE_KEYS}

    out_dir.mkdir(parents=True, exist_ok=True)

    def _render_all() -> int:
        for idx, ft in enumerate(frame_times):
            _render_one(_lerp(ft), ft, out_dir / f"frame_{idx:03d}.jpg")
        return len(frame_times)

    return await asyncio.to_thread(_render_all)
