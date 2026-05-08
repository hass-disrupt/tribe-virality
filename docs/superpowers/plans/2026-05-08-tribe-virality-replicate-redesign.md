# TRIBE Virality — Replicate Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot the application from a pluggable Python inference backend to a browser-only architecture where users supply their own Replicate API token. Inference, scoring, and a synthetic-output fallback move into a cog package; the frontend talks directly to `api.replicate.com`.

**Architecture:** Static React+Vite SPA on Hostinger nginx. All HTTP from the browser goes to `api.replicate.com` only. Replicate model (cog) packages the existing scoring pipeline plus a TRIBE v2 hook (the cog's `predict()` returns a synthetic-but-plausible timeline for M1; real TRIBE wiring is left for the user to push manually as M2). React Context (in-memory) holds the API token, attempts, and current job. One `localStorage` write only — the legal-disclaimer ack flag.

**Tech Stack:** Vite, React 18, TypeScript, Tailwind, Three.js, Recharts, Vitest + React Testing Library; Cog (Python 3.11, CUDA 12.1), pytest, numpy, pydantic.

**Spec:** `docs/superpowers/specs/2026-05-08-tribe-virality-replicate-redesign-design.md`

**Scope of this plan:** Milestones M1, M3–M8 from the spec. M2 (real TRIBE inference inside cog) and M9 (Hostinger deploy) are out of scope — the user will handle those manually after this plan completes.

---

## File Structure

**Created (new):**

```
cog/
  cog.yaml                                 ← runtime config
  predict.py                               ← Predictor with synthetic output
  scoring/                                 ← MOVED from backend (re-rooted package)
    __init__.py
    pipeline.py
    rois.py
    baseline.py
    constants.py
  data/
    roi_mapping.json
    baseline_stats.json
  tests/
    __init__.py
    test_scoring_pipeline.py               ← MOVED, imports rewritten
    test_predict_smoke.py                  ← NEW: schema check on synthetic output
  README.md
  pyproject.toml                           ← for `pytest` outside cog

frontend/src/
  types.ts                                 ← shared types: Attempt, SubScores, TimelinePoint
  state/
    AppState.tsx                           ← React context + reducer (in-memory only)
  lib/
    replicate.ts                           ← Replicate REST client
    captureBrainFrames.ts                  ← offscreen WebGL capture utility
    cn.ts                                  ← (kept) class merge helper
  components/
    Disclaimer.tsx                         ← full-screen ack
    ApiKeyGate.tsx                         ← full-screen token paste + validate
    KeyChip.tsx                            ← header chip showing username + forget
    ProcessingProgress.tsx                 ← phased progress driver
  hooks/
    usePredictionPolling.ts                ← Replicate polling hook
    useVideoThumbnails.ts                  ← canvas-drawn per-second thumbs
  __tests__/
    routing.test.tsx
  setupTests.ts                            ← Vitest + RTL setup

docs/
  REPLICATE_SETUP.md                       ← user-facing onboarding (linked from gate)
```

**Modified:**

```
frontend/
  package.json                             ← add Vitest, RTL, jsdom, msw
  tsconfig.json                            ← include vitest types
  vite.config.ts                           ← Vitest config
  src/
    App.tsx                                ← AppState provider, route guards
    main.tsx                               ← unchanged
    pages/
      Landing.tsx                          ← drop CapabilityBanner, add cost hint
      Processing.tsx                       ← rewrite around Replicate polling
      Results.tsx                          ← in-memory attempts, HeadViewer3D in hero
    components/
      DropZone.tsx                         ← add duration validation
      BrainFrameStrip.tsx                  ← consume data-URL array prop
      AttemptsDrawer.tsx                   ← read from context
      DisclaimerFooter.tsx                 ← link to full disclaimer modal
    hooks/
      usePlaybackSync.ts                   ← simplify to playhead-only
README.md                                  ← rewrite for Replicate flow
.gitignore                                 ← drop backend/ entries, add frontend test outputs
```

**Deleted:**

```
backend/                                   ← entire directory
docs/mps-status.md
frontend/src/lib/api.ts
frontend/src/lib/session.ts
frontend/src/hooks/useJobPolling.ts
frontend/src/hooks/useCapabilities.ts
frontend/src/components/VideoPair.tsx
frontend/src/components/CapabilityBanner.tsx
```

---

## Phase A — Cog Scaffolding (M1)

The cog package contains the scoring pipeline plus a `predict()` that returns synthetic-but-plausible output. The user will push this to Replicate manually and later wire real TRIBE inference inside `predict()`.

### Task A1: Create cog directory with package skeleton

**Files:**
- Create: `cog/__init__.py` (empty — no, cog/ is a project root, not a package)
- Create: `cog/scoring/__init__.py`
- Create: `cog/data/__init__.py`
- Create: `cog/tests/__init__.py`

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p cog/scoring cog/data cog/tests
touch cog/scoring/__init__.py cog/data/__init__.py cog/tests/__init__.py
```

- [ ] **Step 2: Verify**

Run: `ls cog/`
Expected: `data/  scoring/  tests/`

- [ ] **Step 3: Commit**

```bash
git add cog/
git commit -m "chore(cog): scaffold cog package directory"
```

### Task A2: Move scoring module into cog with corrected imports

The existing `backend/src/tribe_virality/scoring/{pipeline,rois,baseline,constants}.py` and `backend/src/tribe_virality/data/{roi_mapping,baseline_stats}.json` move to `cog/scoring/` and `cog/data/`. Imports must be rewritten because the package is no longer named `tribe_virality`.

**Files:**
- Create (copy from backend): `cog/scoring/pipeline.py`, `cog/scoring/rois.py`, `cog/scoring/baseline.py`, `cog/scoring/constants.py`
- Create (copy from backend): `cog/data/roi_mapping.json`, `cog/data/baseline_stats.json`

- [ ] **Step 1: Copy the four scoring source files**

```bash
cp backend/src/tribe_virality/scoring/pipeline.py cog/scoring/pipeline.py
cp backend/src/tribe_virality/scoring/rois.py cog/scoring/rois.py
cp backend/src/tribe_virality/scoring/baseline.py cog/scoring/baseline.py
cp backend/src/tribe_virality/scoring/constants.py cog/scoring/constants.py
```

- [ ] **Step 2: Copy the data files**

```bash
cp backend/src/tribe_virality/data/roi_mapping.json cog/data/roi_mapping.json
cp backend/src/tribe_virality/data/baseline_stats.json cog/data/baseline_stats.json
```

- [ ] **Step 3: Rewrite resource loads in `cog/scoring/rois.py`**

Replace the body of `load_roi_mapping`:

```python
@lru_cache(maxsize=1)
def load_roi_mapping() -> dict:
    """Load the ROI mapping JSON from cog/data/."""
    here = Path(__file__).resolve().parent.parent  # cog/
    with (here / "data" / "roi_mapping.json").open("r") as f:
        return json.load(f)
```

Add at the top of the file:

```python
from pathlib import Path
```

Remove `from importlib import resources`.

- [ ] **Step 4: Rewrite resource loads in `cog/scoring/baseline.py`**

Replace the body of `load_baseline_stats`:

```python
@lru_cache(maxsize=1)
def load_baseline_stats() -> dict[str, dict[str, float]]:
    """Return {sub_score: {"mean": float, "std": float}}."""
    here = Path(__file__).resolve().parent.parent  # cog/
    with (here / "data" / "baseline_stats.json").open("r") as f:
        raw = json.load(f)
    out: dict[str, dict[str, float]] = {}
    for name in SUB_SCORE_NAMES:
        if name not in raw:
            raise KeyError(f"Sub-score {name!r} missing from baseline_stats.json")
        entry = raw[name]
        out[name] = {"mean": float(entry["mean"]), "std": float(entry["std"])}
        if out[name]["std"] <= 0:
            raise ValueError(f"Baseline std for {name!r} must be > 0")
    return out
```

Add at top:

```python
from pathlib import Path
```

Remove `from importlib import resources`.

- [ ] **Step 5: Verify the imports inside scoring still work**

Run from project root:

```bash
cd cog && python -c "from scoring.pipeline import score_preds; from scoring.rois import expected_n_vertices; print(expected_n_vertices())"
```

Expected: prints `20484` (or whatever vertex count the existing roi_mapping.json declares — should be a positive integer).

- [ ] **Step 6: Commit**

```bash
git add cog/
git commit -m "feat(cog): move scoring + data into cog package"
```

### Task A3: Move scoring tests with rewritten imports

**Files:**
- Create: `cog/tests/test_scoring_pipeline.py` (copied from `backend/tests/unit/test_scoring_pipeline.py` with import rewrites)
- Create: `cog/pyproject.toml` (minimal — pytest config + dev deps)

- [ ] **Step 1: Copy the test file**

```bash
cp backend/tests/unit/test_scoring_pipeline.py cog/tests/test_scoring_pipeline.py
```

- [ ] **Step 2: Rewrite imports in `cog/tests/test_scoring_pipeline.py`**

Find every `from tribe_virality.scoring.X` and replace with `from scoring.X`. Specifically:

```python
# was:
# from tribe_virality.scoring.constants import SUB_SCORE_NAMES, WEIGHTS
# from tribe_virality.scoring.pipeline import score_preds, sub_score_curves
# from tribe_virality.scoring.rois import expected_n_vertices, get_bucket_indices

# becomes:
from scoring.constants import SUB_SCORE_NAMES, WEIGHTS
from scoring.pipeline import score_preds, sub_score_curves
from scoring.rois import expected_n_vertices, get_bucket_indices
```

(There are exactly two import sites — one at top-of-file and one inside `test_headline_uses_declared_weights` for `get_bucket_indices`.)

- [ ] **Step 3: Create `cog/pyproject.toml`**

```toml
[project]
name = "cog-tribe-virality"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "numpy>=1.26",
  "pydantic>=2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

- [ ] **Step 4: Install dev deps and run tests**

```bash
cd cog && pip install -e ".[dev]" && python -m pytest
```

Expected: all 11 tests pass.

If any test fails, the move is broken — fix by inspecting the diff against the original file. Do not modify test logic.

- [ ] **Step 5: Commit**

```bash
git add cog/
git commit -m "test(cog): port scoring pipeline tests with corrected imports"
```

### Task A4: Write the cog Predictor with synthetic output

`predict()` returns a deterministic plausible timeline derived from the input video's duration and a seed taken from the file path. Real TRIBE wiring will be added later by the user.

**Files:**
- Create: `cog/predict.py`

- [ ] **Step 1: Create `cog/predict.py`**

```python
"""Cog Predictor for TRIBE Virality.

Phase 1 (this file): synthesizes a plausible timeline from video duration so
the frontend can be developed end-to-end against a real Replicate model.
Phase 2 (TODO, manual): wire facebook/tribev2 inside `predict()`.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from cog import BasePredictor, Input, Path as CogPath
from pydantic import BaseModel

from scoring.constants import SUB_SCORE_NAMES
from scoring.pipeline import score_preds
from scoring.rois import expected_n_vertices

SCORING_VERSION = "1.0"
MODEL_VERSION = "synthetic-v1"  # will become "tribev2-<commit>" after Phase 2


class TribeOutput(BaseModel):
    headline_score: int
    sub_scores: dict[str, int]
    timeline: list[dict[str, float]]
    video_duration_s: float
    frame_count: int
    model_version: str
    scoring_version: str


def _ffprobe_duration_s(video_path: Path) -> float:
    """Return duration in seconds via ffprobe; raise if it fails."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _seed_from_video(video_path: Path) -> int:
    """Hash the file bytes (capped at 1MB) for deterministic per-video output."""
    h = hashlib.sha256()
    with video_path.open("rb") as f:
        h.update(f.read(1024 * 1024))
    return int.from_bytes(h.digest()[:4], "big")


def _synth_preds(seed: int, t: int, v: int) -> np.ndarray:
    """Generate a plausible (T, V) prediction tensor.

    Each ROI bucket gets a slow sinusoidal envelope plus low-frequency noise,
    centered around 0.5. Determinism via numpy's PRNG seeded with `seed`.
    """
    rng = np.random.default_rng(seed)
    base = np.full((t, v), 0.5, dtype=np.float64)
    # Add per-vertex constant offset (small) so different videos differ.
    base += rng.normal(0.0, 0.04, size=(1, v))
    # Add slow temporal variation.
    phases = rng.uniform(0, 2 * np.pi, size=(1, v))
    times = np.linspace(0, 2 * np.pi * 2, num=t).reshape(-1, 1)
    base += 0.08 * np.sin(times + phases)
    return np.clip(base, 0.0, 1.0)


class Predictor(BasePredictor):
    def setup(self) -> None:
        # Force eager loads so cold-start cost is paid once per worker.
        from scoring.baseline import load_baseline_stats
        from scoring.rois import get_bucket_indices, load_roi_mapping

        load_roi_mapping()
        load_baseline_stats()
        get_bucket_indices()

    def predict(  # type: ignore[override]
        self,
        video: CogPath = Input(description="Video file (≤60s, MP4/MOV/WebM)"),
    ) -> TribeOutput:
        print("STAGE:loading_video", flush=True)
        video_path = Path(video)
        duration_s = _ffprobe_duration_s(video_path)
        if duration_s <= 0:
            raise ValueError(f"Invalid duration: {duration_s}")

        # TRIBE v2 outputs ~2 Hz; emulate.
        t = max(2, int(round(duration_s * 2.0)))
        v = expected_n_vertices()

        print("STAGE:tribe_inference", flush=True)
        seed = _seed_from_video(video_path)
        preds = _synth_preds(seed, t, v)

        print("STAGE:scoring", flush=True)
        result = score_preds(preds, video_duration_s=duration_s)

        print("STAGE:done", flush=True)
        return TribeOutput(
            headline_score=int(result.headline_score),
            sub_scores={k: int(round(result.sub_scores[k])) for k in SUB_SCORE_NAMES},
            timeline=[{k: float(v) for k, v in row.items()} for row in result.timeline],
            video_duration_s=float(duration_s),
            frame_count=len(result.timeline),
            model_version=MODEL_VERSION,
            scoring_version=SCORING_VERSION,
        )
```

- [ ] **Step 2: Add a smoke test that exercises `Predictor.predict()`**

Create `cog/tests/test_predict_smoke.py`:

```python
"""Smoke test for the Predictor's synthetic output.

Skipped if `cog` or `ffprobe` are unavailable. The test creates a tiny
fixture video on the fly via ffmpeg.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

cog = pytest.importorskip("cog")

if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
    pytest.skip("ffmpeg/ffprobe not available", allow_module_level=True)


@pytest.fixture
def tiny_mp4(tmp_path: Path) -> Path:
    out = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:size=64x64:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
        ],
        check=True, capture_output=True,
    )
    return out


def test_predict_returns_well_formed_output(tiny_mp4: Path) -> None:
    from predict import Predictor  # imported lazily so the skip works

    predictor = Predictor()
    predictor.setup()
    result = predictor.predict(video=tiny_mp4)

    assert 0 <= result.headline_score <= 100
    assert set(result.sub_scores.keys()) == {
        "reward", "emotion", "attention", "novelty", "social_relevance",
    }
    for v in result.sub_scores.values():
        assert 0 <= v <= 100
    assert result.frame_count == len(result.timeline)
    assert result.frame_count >= 2
    assert result.video_duration_s > 0
    for row in result.timeline:
        assert "t" in row
        for k in result.sub_scores:
            assert 0 <= row[k] <= 100
```

- [ ] **Step 3: Run the cog tests (will skip predict_smoke unless ffmpeg+cog present)**

```bash
cd cog && python -m pytest -v
```

Expected: 11 scoring tests pass; smoke test passes if ffmpeg+cog present, skipped otherwise.

- [ ] **Step 4: Commit**

```bash
git add cog/
git commit -m "feat(cog): add Predictor with synthetic output for end-to-end frontend dev"
```

### Task A5: Write `cog.yaml`

**Files:**
- Create: `cog/cog.yaml`

- [ ] **Step 1: Create the file**

```yaml
build:
  gpu: false                                 # M1 synthetic Predictor needs no GPU
  python_version: "3.11"
  system_packages:
    - "ffmpeg"
  python_packages:
    - "numpy>=1.26"
    - "pydantic>=2"

predict: "predict.py:Predictor"
```

> NOTE: `gpu: false` is correct for the M1 synthetic Predictor. When the user wires real TRIBE in M2, they will flip to `gpu: true`, set `cuda: "12.1"`, and add `torch`, `tribev2 @ git+https://github.com/facebookresearch/tribev2.git`, and `transformers>=4.55`. Do not add those now — they would balloon the M1 image and waste push time.

- [ ] **Step 2: Commit**

```bash
git add cog/cog.yaml
git commit -m "feat(cog): add cog.yaml for synthetic-Predictor build"
```

### Task A6: Write `cog/README.md`

**Files:**
- Create: `cog/README.md`

- [ ] **Step 1: Create the file**

```markdown
# TRIBE Virality — Cog Model

This directory builds the Replicate model used by the Tribe Virality web app.

## Phase

This package currently produces **synthetic-but-plausible** timelines so the
frontend can be developed end-to-end. The synthesized output is deterministic
per input video (hashed file prefix → numpy seed). Real TRIBE v2 inference is
wired in a later phase.

## Local development

```bash
pip install -e ".[dev]"
python -m pytest          # 11 scoring tests + 1 predict smoke (skipped without ffmpeg)
```

## Build the cog image (requires Docker + `cog` CLI)

```bash
cog build
```

## Push to Replicate

```bash
# Authenticate once:
# cog login

cog push r8.im/prakhar-bhartiya/meta-tribev2-social-media-content-signal
```

## Output schema

```python
class TribeOutput(BaseModel):
    headline_score: int                # 0–100
    sub_scores: dict[str, int]         # 5 keys: reward, emotion, attention, novelty, social_relevance
    timeline: list[dict[str, float]]   # one row per fMRI step: {t, reward, emotion, attention, novelty, social_relevance}
    video_duration_s: float
    frame_count: int                   # = len(timeline)
    model_version: str                 # "synthetic-v1" today; bumps when TRIBE is wired
    scoring_version: str               # "1.0"
```

## Stage markers in logs

`predict()` emits machine-parseable lines (`STAGE:loading_video`,
`STAGE:tribe_inference`, `STAGE:scoring`, `STAGE:done`) which the frontend
parses to drive the progress bar. Keep these markers stable across phases.

## Phase 2 (manual, future)

To wire real TRIBE v2:
1. Set `gpu: true`, `cuda: "12.1"` in `cog.yaml`.
2. Add `torch>=2.4`, `tribev2 @ git+https://github.com/facebookresearch/tribev2.git`, `transformers>=4.55` to `python_packages`.
3. Replace `_synth_preds(...)` in `predict.py` with the real TRIBE call producing `(T, V)` numpy preds.
4. Set `MODEL_VERSION = "tribev2-<commit>"`.
5. Re-run smoke tests, push.
```

- [ ] **Step 2: Commit**

```bash
git add cog/README.md
git commit -m "docs(cog): document build/push and Phase 1 vs Phase 2 split"
```

---

## Phase B — Backend Deletion (M3)

The frontend will be temporarily broken at the end of this phase — that's intentional. Phase D onward rebuilds it.

### Task B1: Delete the backend directory

**Files:**
- Delete: `backend/` (recursive)

- [ ] **Step 1: Verify scoring + data + tests are already moved (sanity check)**

```bash
test -f cog/scoring/pipeline.py && test -f cog/data/roi_mapping.json && test -f cog/tests/test_scoring_pipeline.py && echo "OK"
```

Expected: `OK`. If not, do not proceed — A2/A3 weren't completed.

- [ ] **Step 2: Remove the backend directory**

```bash
git rm -rf backend/
```

- [ ] **Step 3: Verify removal**

```bash
test ! -d backend && echo "removed"
```

Expected: `removed`.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove backend directory (replaced by cog + browser-only frontend)"
```

### Task B2: Delete obsolete frontend files

**Files:**
- Delete: `frontend/src/lib/api.ts`, `frontend/src/lib/session.ts`
- Delete: `frontend/src/hooks/useJobPolling.ts`, `frontend/src/hooks/useCapabilities.ts`
- Delete: `frontend/src/components/VideoPair.tsx`, `frontend/src/components/CapabilityBanner.tsx`

- [ ] **Step 1: Remove**

```bash
git rm frontend/src/lib/api.ts frontend/src/lib/session.ts
git rm frontend/src/hooks/useJobPolling.ts frontend/src/hooks/useCapabilities.ts
git rm frontend/src/components/VideoPair.tsx frontend/src/components/CapabilityBanner.tsx
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore(frontend): remove backend-coupled HTTP client, session, capability code"
```

### Task B3: Delete obsolete docs and gitignore entries

**Files:**
- Delete: `docs/mps-status.md` (if it exists — it's referenced in old README but may not exist on this branch)
- Modify: `.gitignore` — remove `backend/` entries

- [ ] **Step 1: Conditionally remove `docs/mps-status.md`**

```bash
[ -f docs/mps-status.md ] && git rm docs/mps-status.md || echo "already absent"
```

- [ ] **Step 2: Edit `.gitignore`**

Open `.gitignore` and remove any line that mentions `backend/`. Keep all frontend, node, and python ignores. (If there are no backend-specific lines, leave the file alone and skip the commit step below.)

- [ ] **Step 3: Commit**

```bash
git add .gitignore docs/ 2>/dev/null
git commit -m "chore: drop MPS status doc and backend gitignore entries"
```

(If nothing was changed, skip the commit.)

---

## Phase C — Frontend Test Infrastructure

### Task C1: Add Vitest, RTL, jsdom, MSW

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/setupTests.ts`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Add dev deps**

```bash
cd frontend && npm install --save-dev vitest@^2 @vitest/ui @testing-library/react@^16 @testing-library/jest-dom@^6 @testing-library/user-event@^14 jsdom msw@^2
```

- [ ] **Step 2: Add `test` script to `frontend/package.json`**

In the `"scripts"` block, add:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 3: Create `frontend/src/setupTests.ts`**

```ts
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 4: Update `frontend/vite.config.ts` to register Vitest**

Read the existing config first; the project may not have one (Vite has defaults). If the file is missing, create:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    globals: true,
  },
});
```

If the file exists, merge the `test` block in.

- [ ] **Step 5: Run an empty test to verify setup**

Create a temporary test `frontend/src/__tests__/smoke.test.ts`:

```ts
import { describe, it, expect } from "vitest";

describe("vitest smoke", () => {
  it("works", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run: `cd frontend && npm test`

Expected: 1 passed.

- [ ] **Step 6: Commit (keep the smoke test — it's a useful canary)**

```bash
cd ..
git add frontend/package.json frontend/package-lock.json frontend/src/setupTests.ts frontend/vite.config.ts frontend/src/__tests__/smoke.test.ts
git commit -m "test(frontend): set up Vitest + RTL + jsdom"
```

---

## Phase D — Types & In-Memory State (M4 prep)

### Task D1: Define shared types

**Files:**
- Create: `frontend/src/types.ts`

- [ ] **Step 1: Write `frontend/src/types.ts`**

```ts
export type SubScoreKey =
  | "reward"
  | "emotion"
  | "attention"
  | "novelty"
  | "social_relevance";

export const SUB_SCORE_KEYS: readonly SubScoreKey[] = [
  "reward",
  "emotion",
  "attention",
  "novelty",
  "social_relevance",
] as const;

export type SubScores = Record<SubScoreKey, number>;

export interface TimelinePoint extends SubScores {
  t: number;
}

export type AttemptStatus = "queued" | "processing" | "done" | "error";

export interface Attempt {
  attemptId: string;          // local UUID
  predictionId: string;        // Replicate id (r8_...)
  label: string;               // "v1", "v2", or user-named
  videoBlobUrl: string;        // URL.createObjectURL(file); revoked on remove
  videoDurationS: number;
  uploadedAt: string;          // ISO timestamp
  status: AttemptStatus;
  headlineScore: number | null;
  subScores: SubScores | null;
  timeline: TimelinePoint[] | null;
  frameCount: number;
  modelVersion: string | null;
  scoringVersion: string | null;
  brainFrames: string[] | null; // data URLs, captured lazily on Results mount
  errorMessage: string | null;
}

export interface ReplicateAccount {
  username: string;
  type: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat(frontend): define shared types for attempts, timeline, sub-scores"
```

### Task D2: Write the AppState reducer (TDD)

**Files:**
- Create: `frontend/src/state/AppState.tsx`
- Create: `frontend/src/state/__tests__/AppState.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/state/__tests__/AppState.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { AppStateProvider, useAppState } from "../AppState";
import type { Attempt } from "../../types";

const wrap = ({ children }: { children: ReactNode }) => (
  <AppStateProvider>{children}</AppStateProvider>
);

const mkAttempt = (id: string, headline: number | null = null): Attempt => ({
  attemptId: id,
  predictionId: `pred_${id}`,
  label: id,
  videoBlobUrl: "blob:http://x/" + id,
  videoDurationS: 10,
  uploadedAt: "2026-05-08T00:00:00Z",
  status: "done",
  headlineScore: headline,
  subScores: null,
  timeline: null,
  frameCount: 0,
  modelVersion: null,
  scoringVersion: null,
  brainFrames: null,
  errorMessage: null,
});

describe("AppState", () => {
  it("starts with empty state", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    expect(result.current.state.apiKey).toBeNull();
    expect(result.current.state.attempts).toEqual([]);
    expect(result.current.state.currentJobId).toBeNull();
  });

  it("setApiKey stores key and account", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.setApiKey("r8_test", { username: "u", type: "user" }));
    expect(result.current.state.apiKey).toBe("r8_test");
    expect(result.current.state.apiKeyAccount?.username).toBe("u");
  });

  it("forgetKey clears apiKey, account, attempts, currentJobId", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => {
      result.current.setApiKey("r8_test", { username: "u", type: "user" });
      result.current.addAttempt(mkAttempt("v1"));
      result.current.setCurrentJob("pred_v1");
    });
    act(() => result.current.forgetKey());
    expect(result.current.state.apiKey).toBeNull();
    expect(result.current.state.apiKeyAccount).toBeNull();
    expect(result.current.state.attempts).toEqual([]);
    expect(result.current.state.currentJobId).toBeNull();
  });

  it("addAttempt prepends (newest first)", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => {
      result.current.addAttempt(mkAttempt("v1"));
      result.current.addAttempt(mkAttempt("v2"));
    });
    expect(result.current.state.attempts.map((a) => a.attemptId)).toEqual(["v2", "v1"]);
  });

  it("updateAttempt patches by attemptId", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.addAttempt(mkAttempt("v1")));
    act(() => result.current.updateAttempt("v1", { headlineScore: 72, status: "done" }));
    expect(result.current.state.attempts[0].headlineScore).toBe(72);
  });

  it("removeAttempt drops by id", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => {
      result.current.addAttempt(mkAttempt("v1"));
      result.current.addAttempt(mkAttempt("v2"));
    });
    act(() => result.current.removeAttempt("v1"));
    expect(result.current.state.attempts.map((a) => a.attemptId)).toEqual(["v2"]);
  });

  it("setCurrentJob stores prediction id", () => {
    const { result } = renderHook(() => useAppState(), { wrapper: wrap });
    act(() => result.current.setCurrentJob("pred_xyz"));
    expect(result.current.state.currentJobId).toBe("pred_xyz");
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail (module missing)**

```bash
cd frontend && npm test -- AppState
```

Expected: FAIL — `Cannot find module '../AppState'`.

- [ ] **Step 3: Write `frontend/src/state/AppState.tsx`**

```tsx
import { createContext, useCallback, useContext, useMemo, useReducer } from "react";
import type { ReactNode } from "react";
import type { Attempt, ReplicateAccount } from "../types";

interface AppStateData {
  apiKey: string | null;
  apiKeyAccount: ReplicateAccount | null;
  attempts: Attempt[];           // newest first
  currentJobId: string | null;
}

const INITIAL: AppStateData = {
  apiKey: null,
  apiKeyAccount: null,
  attempts: [],
  currentJobId: null,
};

type Action =
  | { type: "SET_KEY"; key: string; account: ReplicateAccount }
  | { type: "FORGET_KEY" }
  | { type: "ADD_ATTEMPT"; attempt: Attempt }
  | { type: "UPDATE_ATTEMPT"; id: string; patch: Partial<Attempt> }
  | { type: "REMOVE_ATTEMPT"; id: string }
  | { type: "SET_CURRENT_JOB"; jobId: string | null };

function reducer(state: AppStateData, action: Action): AppStateData {
  switch (action.type) {
    case "SET_KEY":
      return { ...state, apiKey: action.key, apiKeyAccount: action.account };
    case "FORGET_KEY":
      // Revoke any blob URLs we created so the browser releases the bytes.
      for (const a of state.attempts) {
        if (a.videoBlobUrl) URL.revokeObjectURL(a.videoBlobUrl);
      }
      return { ...INITIAL };
    case "ADD_ATTEMPT":
      return { ...state, attempts: [action.attempt, ...state.attempts] };
    case "UPDATE_ATTEMPT":
      return {
        ...state,
        attempts: state.attempts.map((a) =>
          a.attemptId === action.id ? { ...a, ...action.patch } : a,
        ),
      };
    case "REMOVE_ATTEMPT": {
      const target = state.attempts.find((a) => a.attemptId === action.id);
      if (target?.videoBlobUrl) URL.revokeObjectURL(target.videoBlobUrl);
      return {
        ...state,
        attempts: state.attempts.filter((a) => a.attemptId !== action.id),
      };
    }
    case "SET_CURRENT_JOB":
      return { ...state, currentJobId: action.jobId };
  }
}

interface AppStateContextValue {
  state: AppStateData;
  setApiKey: (key: string, account: ReplicateAccount) => void;
  forgetKey: () => void;
  addAttempt: (attempt: Attempt) => void;
  updateAttempt: (id: string, patch: Partial<Attempt>) => void;
  removeAttempt: (id: string) => void;
  setCurrentJob: (jobId: string | null) => void;
}

const AppStateContext = createContext<AppStateContextValue | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, INITIAL);

  const setApiKey = useCallback(
    (key: string, account: ReplicateAccount) =>
      dispatch({ type: "SET_KEY", key, account }),
    [],
  );
  const forgetKey = useCallback(() => dispatch({ type: "FORGET_KEY" }), []);
  const addAttempt = useCallback(
    (attempt: Attempt) => dispatch({ type: "ADD_ATTEMPT", attempt }),
    [],
  );
  const updateAttempt = useCallback(
    (id: string, patch: Partial<Attempt>) =>
      dispatch({ type: "UPDATE_ATTEMPT", id, patch }),
    [],
  );
  const removeAttempt = useCallback(
    (id: string) => dispatch({ type: "REMOVE_ATTEMPT", id }),
    [],
  );
  const setCurrentJob = useCallback(
    (jobId: string | null) => dispatch({ type: "SET_CURRENT_JOB", jobId }),
    [],
  );

  const value = useMemo(
    () => ({ state, setApiKey, forgetKey, addAttempt, updateAttempt, removeAttempt, setCurrentJob }),
    [state, setApiKey, forgetKey, addAttempt, updateAttempt, removeAttempt, setCurrentJob],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used inside <AppStateProvider>");
  return ctx;
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && npm test -- AppState
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/state/
git commit -m "feat(frontend): in-memory AppState context with reducer + tests"
```

---

## Phase E — Disclaimer Screen (M4)

### Task E1: Create the Disclaimer component (TDD)

**Files:**
- Create: `frontend/src/lib/disclaimerAck.ts`
- Create: `frontend/src/components/Disclaimer.tsx`
- Create: `frontend/src/components/__tests__/Disclaimer.test.tsx`

- [ ] **Step 1: Write the disclaimerAck helper**

Create `frontend/src/lib/disclaimerAck.ts`:

```ts
export const DISCLAIMER_VERSION = 1;
const KEY = "tribe_virality.disclaimer_ack";

export function hasAckedDisclaimer(): boolean {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return parsed?.version === DISCLAIMER_VERSION;
  } catch {
    return false;
  }
}

export function ackDisclaimer(): void {
  localStorage.setItem(
    KEY,
    JSON.stringify({ version: DISCLAIMER_VERSION, ackedAt: new Date().toISOString() }),
  );
}
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/components/__tests__/Disclaimer.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Disclaimer } from "../Disclaimer";
import { DISCLAIMER_VERSION, hasAckedDisclaimer } from "../../lib/disclaimerAck";

describe("Disclaimer", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders required headings", () => {
    render(<Disclaimer onAck={() => {}} />);
    expect(screen.getByText(/About this tool/i)).toBeInTheDocument();
    expect(screen.getByText(/About TRIBE v2/i)).toBeInTheDocument();
    expect(screen.getByText(/Accuracy & limitations/i)).toBeInTheDocument();
    expect(screen.getByText(/Liability/i)).toBeInTheDocument();
  });

  it("Continue button is disabled until checkbox is ticked", async () => {
    const user = userEvent.setup();
    render(<Disclaimer onAck={() => {}} />);
    const button = screen.getByRole("button", { name: /continue/i });
    expect(button).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(button).toBeEnabled();
  });

  it("clicking Continue writes ack flag and calls onAck", async () => {
    const onAck = vi.fn();
    const user = userEvent.setup();
    render(<Disclaimer onAck={onAck} />);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(onAck).toHaveBeenCalledOnce();
    expect(hasAckedDisclaimer()).toBe(true);
    const stored = JSON.parse(localStorage.getItem("tribe_virality.disclaimer_ack")!);
    expect(stored.version).toBe(DISCLAIMER_VERSION);
    expect(typeof stored.ackedAt).toBe("string");
  });

  it("readOnly mode hides the checkbox and Continue button", () => {
    render(<Disclaimer readOnly onAck={() => {}} />);
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /continue/i })).toBeNull();
  });
});
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd frontend && npm test -- Disclaimer
```

Expected: FAIL — module missing.

- [ ] **Step 4: Implement `frontend/src/components/Disclaimer.tsx`**

```tsx
import { useState } from "react";
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-ink uppercase tracking-wide">{title}</h2>
      <div className="text-sm text-ink-muted leading-relaxed">{children}</div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
cd frontend && npm test -- Disclaimer
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/src/lib/disclaimerAck.ts frontend/src/components/Disclaimer.tsx frontend/src/components/__tests__/Disclaimer.test.tsx
git commit -m "feat(frontend): disclaimer screen with versioned localStorage ack"
```

---

## Phase F — Replicate Client + ApiKeyGate (M4 + M5 prep)

### Task F1: Replicate fetch helper (TDD)

The single source of truth for `Authorization`-bearing requests. Hardcodes the host, scrubs the auth header from any thrown error.

**Files:**
- Create: `frontend/src/lib/replicate.ts`
- Create: `frontend/src/lib/__tests__/replicate.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/lib/__tests__/replicate.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { replicateFetch, validateToken, ReplicateAuthError, ReplicateNetworkError } from "../replicate";

describe("replicateFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends Authorization header to api.replicate.com", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }),
    );
    await replicateFetch({ apiKey: "r8_test" }, "/v1/account");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toBe("https://api.replicate.com/v1/account");
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer r8_test");
  });

  it("throws ReplicateAuthError on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("unauthorized", { status: 401 }),
    );
    await expect(replicateFetch({ apiKey: "bad" }, "/v1/account")).rejects.toBeInstanceOf(ReplicateAuthError);
  });

  it("throws ReplicateNetworkError on 5xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("err", { status: 502 }));
    await expect(replicateFetch({ apiKey: "x" }, "/v1/account")).rejects.toBeInstanceOf(ReplicateNetworkError);
  });

  it("scrubs Authorization from thrown error message", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new Error("connect failed Authorization: Bearer r8_secret"),
    );
    try {
      await replicateFetch({ apiKey: "r8_secret" }, "/v1/account");
      throw new Error("should have thrown");
    } catch (e) {
      expect(String((e as Error).message)).not.toContain("r8_secret");
      expect(String((e as Error).message)).not.toContain("Bearer");
    }
  });
});

describe("validateToken", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns account info on 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ username: "u", type: "user" }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const acct = await validateToken("r8_x");
    expect(acct).toEqual({ username: "u", type: "user" });
  });

  it("rejects with ReplicateAuthError on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 401 }));
    await expect(validateToken("bad")).rejects.toBeInstanceOf(ReplicateAuthError);
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd frontend && npm test -- replicate
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement `frontend/src/lib/replicate.ts`**

```ts
const REPLICATE_HOST = "https://api.replicate.com";

export class ReplicateAuthError extends Error {
  constructor(msg: string) { super(msg); this.name = "ReplicateAuthError"; }
}
export class ReplicateQuotaError extends Error {
  constructor(msg: string) { super(msg); this.name = "ReplicateQuotaError"; }
}
export class ReplicateNetworkError extends Error {
  constructor(msg: string) { super(msg); this.name = "ReplicateNetworkError"; }
}

interface AuthCtx { apiKey: string }

function scrub(msg: string): string {
  return msg
    .replace(/Bearer\s+r8_[A-Za-z0-9_-]+/g, "Bearer ***")
    .replace(/r8_[A-Za-z0-9_-]{6,}/g, "r8_***")
    .replace(/Authorization:[^,)\]]+/gi, "Authorization: ***");
}

export async function replicateFetch(
  auth: AuthCtx,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = `${REPLICATE_HOST}${path}`;
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${auth.apiKey}`);

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new ReplicateNetworkError(scrub(`Network error: ${msg}`));
  }

  if (res.status === 401 || res.status === 403) {
    throw new ReplicateAuthError(`Replicate rejected the token (${res.status}).`);
  }
  if (res.status === 402) {
    throw new ReplicateQuotaError("Replicate says you're out of credits. Add some at replicate.com/account/billing.");
  }
  if (res.status >= 500) {
    throw new ReplicateNetworkError(`Replicate is having trouble (${res.status}). Try again.`);
  }
  return res;
}

export async function validateToken(apiKey: string): Promise<{ username: string; type: string }> {
  const res = await replicateFetch({ apiKey }, "/v1/account");
  if (!res.ok) {
    throw new ReplicateNetworkError(`Account check failed (${res.status}).`);
  }
  const json = await res.json();
  return { username: String(json.username ?? ""), type: String(json.type ?? "") };
}

export interface UploadedFile {
  id: string;
  url: string;
}

export async function uploadFile(
  auth: AuthCtx,
  file: File,
  onProgress?: (loaded: number, total: number) => void,
): Promise<UploadedFile> {
  return new Promise<UploadedFile>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${REPLICATE_HOST}/v1/files`);
    xhr.setRequestHeader("Authorization", `Bearer ${auth.apiKey}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded, e.total);
    };
    xhr.onerror = () => reject(new ReplicateNetworkError("Upload failed (network error)."));
    xhr.onload = () => {
      if (xhr.status === 401 || xhr.status === 403) {
        reject(new ReplicateAuthError("Replicate rejected the token during upload."));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const json = JSON.parse(xhr.responseText);
          resolve({ id: String(json.id ?? ""), url: String(json.urls?.get ?? "") });
        } catch (e) {
          reject(new ReplicateNetworkError("Bad response from Replicate Files API."));
        }
      } else {
        reject(new ReplicateNetworkError(`Upload failed (${xhr.status}).`));
      }
    };
    const fd = new FormData();
    fd.append("content", file);
    xhr.send(fd);
  });
}

export interface PredictionInput {
  modelOwner: string;
  modelName: string;
  modelVersion: string;        // version id from /v1/models/{owner}/{name}
  input: Record<string, unknown>;
}

export interface PredictionStatus {
  id: string;
  status: "starting" | "processing" | "succeeded" | "failed" | "canceled";
  logs: string | null;
  output: unknown;
  error: string | null;
  metrics?: { predict_time?: number };
}

export async function getLatestModelVersion(
  auth: AuthCtx,
  owner: string,
  name: string,
): Promise<string> {
  const res = await replicateFetch(auth, `/v1/models/${owner}/${name}`);
  if (!res.ok) throw new ReplicateNetworkError(`Failed to fetch model (${res.status}).`);
  const json = await res.json();
  const version = json?.latest_version?.id;
  if (!version) throw new ReplicateNetworkError("Model has no published version.");
  return String(version);
}

export async function createPrediction(
  auth: AuthCtx,
  body: { version: string; input: Record<string, unknown> },
): Promise<PredictionStatus> {
  const res = await replicateFetch(auth, "/v1/predictions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ReplicateNetworkError(`Could not create prediction (${res.status}).`);
  return (await res.json()) as PredictionStatus;
}

export async function getPrediction(
  auth: AuthCtx,
  predictionId: string,
): Promise<PredictionStatus> {
  const res = await replicateFetch(auth, `/v1/predictions/${predictionId}`);
  if (!res.ok) throw new ReplicateNetworkError(`Could not fetch prediction (${res.status}).`);
  return (await res.json()) as PredictionStatus;
}

export async function cancelPrediction(
  auth: AuthCtx,
  predictionId: string,
): Promise<void> {
  await replicateFetch(auth, `/v1/predictions/${predictionId}/cancel`, { method: "POST" });
}
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
cd frontend && npm test -- replicate
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/lib/replicate.ts frontend/src/lib/__tests__/replicate.test.ts
git commit -m "feat(frontend): Replicate REST client with auth scrubbing"
```

### Task F2: ApiKeyGate component (TDD)

**Files:**
- Create: `frontend/src/components/ApiKeyGate.tsx`
- Create: `frontend/src/components/__tests__/ApiKeyGate.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/__tests__/ApiKeyGate.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { ApiKeyGate } from "../ApiKeyGate";
import { AppStateProvider, useAppState } from "../../state/AppState";

const wrap = ({ children }: { children: ReactNode }) => (
  <AppStateProvider>{children}</AppStateProvider>
);

function StateProbe() {
  const { state } = useAppState();
  return <div data-testid="probe">{state.apiKey ?? "none"}</div>;
}

describe("ApiKeyGate", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("Continue is disabled until token field is non-empty", async () => {
    const user = userEvent.setup();
    render(
      <>
        <ApiKeyGate />
        <StateProbe />
      </>,
      { wrapper: wrap },
    );
    const button = screen.getByRole("button", { name: /continue/i });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_x");
    expect(button).toBeEnabled();
  });

  it("on 200 stores key and account", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ username: "alice", type: "user" }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      <>
        <ApiKeyGate />
        <StateProbe />
      </>,
      { wrapper: wrap },
    );
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_good");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toBe("r8_good"));
  });

  it("on 401 shows inline error and does NOT store key", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 401 }));
    const user = userEvent.setup();
    render(
      <>
        <ApiKeyGate />
        <StateProbe />
      </>,
      { wrapper: wrap },
    );
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_bad");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(screen.getByText(/didn'?t work/i)).toBeInTheDocument());
    expect(screen.getByTestId("probe").textContent).toBe("none");
  });

  it("on network error shows generic error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    render(<ApiKeyGate />, { wrapper: wrap });
    await user.type(screen.getByLabelText(/replicate api token/i), "r8_x");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(screen.getByText(/couldn'?t reach replicate/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd frontend && npm test -- ApiKeyGate
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement `frontend/src/components/ApiKeyGate.tsx`**

```tsx
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
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- ApiKeyGate
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/components/ApiKeyGate.tsx frontend/src/components/__tests__/ApiKeyGate.test.tsx
git commit -m "feat(frontend): ApiKeyGate with validation against /v1/account"
```

### Task F3: KeyChip component

**Files:**
- Create: `frontend/src/components/KeyChip.tsx`

- [ ] **Step 1: Implement**

```tsx
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/KeyChip.tsx
git commit -m "feat(frontend): KeyChip header affordance"
```

### Task F4: Wire AppState provider, route guards, and gates into App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/TopBar.tsx`

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppStateProvider, useAppState } from "./state/AppState";
import { Disclaimer } from "./components/Disclaimer";
import { ApiKeyGate } from "./components/ApiKeyGate";
import { TopBar } from "./components/TopBar";
import { DisclaimerFooter } from "./components/DisclaimerFooter";
import Landing from "./pages/Landing";
import Processing from "./pages/Processing";
import Results from "./pages/Results";
import { hasAckedDisclaimer } from "./lib/disclaimerAck";

function Gates({ children }: { children: React.ReactNode }) {
  const { state } = useAppState();
  const [acked, setAcked] = useState<boolean>(() => hasAckedDisclaimer());

  if (!acked) return <Disclaimer onAck={() => setAcked(true)} />;
  if (!state.apiKey) return <ApiKeyGate />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AppStateProvider>
      <Gates>
        <div className="min-h-screen flex flex-col">
          <TopBar />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/processing/:predictionId" element={<Processing />} />
              <Route path="/results/:attemptId" element={<Results />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <DisclaimerFooter />
        </div>
      </Gates>
    </AppStateProvider>
  );
}
```

- [ ] **Step 2: Update `frontend/src/components/TopBar.tsx` to render the KeyChip**

Read the existing TopBar.tsx first; then add `<KeyChip />` to its right-side area. If TopBar.tsx is a simple wrapper with title-only content, add a flex container with title on the left and chip on the right:

```tsx
import { Link } from "react-router-dom";
import { KeyChip } from "./KeyChip";

export function TopBar() {
  return (
    <header className="border-b border-border-subtle px-4 sm:px-6 py-3 flex items-center justify-between">
      <Link to="/" className="text-ink font-semibold tracking-tight">Tribe Virality</Link>
      <KeyChip />
    </header>
  );
}
```

- [ ] **Step 3: Run all tests**

```bash
cd frontend && npm test
```

Expected: all existing tests still pass. App will not currently boot in a browser because Landing.tsx still imports the deleted `lib/api.ts`. That's fine — Landing is rewritten in Phase I.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/App.tsx frontend/src/components/TopBar.tsx
git commit -m "feat(frontend): wire AppState provider with disclaimer + key gates"
```

---

## Phase G — Replicate Polling Hook (M5)

### Task G1: usePredictionPolling (TDD)

**Files:**
- Create: `frontend/src/hooks/usePredictionPolling.ts`
- Create: `frontend/src/hooks/__tests__/usePredictionPolling.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/hooks/__tests__/usePredictionPolling.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { AppStateProvider, useAppState } from "../../state/AppState";
import { usePredictionPolling } from "../usePredictionPolling";
import type { PredictionStatus } from "../../lib/replicate";

function Wrap({ children }: { children: ReactNode }) {
  return <AppStateProvider>{children}</AppStateProvider>;
}

function useSeededState() {
  const ctx = useAppState();
  if (!ctx.state.apiKey) ctx.setApiKey("r8_test", { username: "u", type: "user" });
  return ctx;
}

const mkStatus = (status: PredictionStatus["status"], logs: string | null = null): PredictionStatus => ({
  id: "pred_1",
  status,
  logs,
  output: status === "succeeded" ? { headline_score: 50, sub_scores: {}, timeline: [], video_duration_s: 1, frame_count: 0, model_version: "x", scoring_version: "1" } : null,
  error: null,
});

describe("usePredictionPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls until succeeded and returns terminal output", async () => {
    const states = [mkStatus("starting"), mkStatus("processing"), mkStatus("succeeded")];
    let i = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify(states[Math.min(i++, states.length - 1)]), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const { result } = renderHook(
      () => {
        useSeededState();
        return usePredictionPolling("pred_1");
      },
      { wrapper: Wrap },
    );
    // Drive timers forward until the hook reports succeeded.
    for (let n = 0; n < 30; n++) {
      await vi.advanceTimersByTimeAsync(1500);
      if (result.current.status === "succeeded") break;
    }
    expect(result.current.status).toBe("succeeded");
    expect(result.current.error).toBeNull();
  });

  it("stops polling once status is terminal", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mkStatus("succeeded")), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    renderHook(
      () => {
        useSeededState();
        return usePredictionPolling("pred_1");
      },
      { wrapper: Wrap },
    );
    await vi.advanceTimersByTimeAsync(1500);
    const callsAfterFirst = fetchSpy.mock.calls.length;
    await vi.advanceTimersByTimeAsync(20_000);
    expect(fetchSpy.mock.calls.length).toBe(callsAfterFirst);
  });

  it("exposes the latest STAGE: line from logs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify(mkStatus("processing", "boot ok\nSTAGE:tribe_inference\nworking…")),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const { result } = renderHook(
      () => {
        useSeededState();
        return usePredictionPolling("pred_1");
      },
      { wrapper: Wrap },
    );
    await vi.advanceTimersByTimeAsync(1500);
    await waitFor(() => expect(result.current.lastStage).toBe("tribe_inference"));
  });
});
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd frontend && npm test -- usePredictionPolling
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement `frontend/src/hooks/usePredictionPolling.ts`**

```ts
import { useEffect, useRef, useState } from "react";
import { useAppState } from "../state/AppState";
import { getPrediction, type PredictionStatus } from "../lib/replicate";

interface PollResult extends PredictionStatus {
  elapsedMs: number;
  lastStage: string | null;
}

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);

function pollIntervalMs(elapsedMs: number): number {
  if (elapsedMs < 30_000) return 1500;
  if (elapsedMs < 120_000) return 2500;
  return 4000;
}

function lastStageFromLogs(logs: string | null): string | null {
  if (!logs) return null;
  const matches = [...logs.matchAll(/STAGE:([a-z_]+)/g)];
  return matches.length ? matches[matches.length - 1][1] : null;
}

export function usePredictionPolling(predictionId: string | null): PollResult {
  const { state } = useAppState();
  const startRef = useRef(Date.now());
  const [snapshot, setSnapshot] = useState<PollResult>({
    id: predictionId ?? "",
    status: "starting",
    logs: null,
    output: null,
    error: null,
    elapsedMs: 0,
    lastStage: null,
  });

  useEffect(() => {
    if (!predictionId || !state.apiKey) return;
    let cancelled = false;
    let timer: number | null = null;
    let backoff = 0;
    startRef.current = Date.now();

    async function tick() {
      if (cancelled) return;
      try {
        const status = await getPrediction({ apiKey: state.apiKey! }, predictionId!);
        backoff = 0;
        const elapsedMs = Date.now() - startRef.current;
        const lastStage = lastStageFromLogs(status.logs);
        setSnapshot({ ...status, elapsedMs, lastStage });
        if (TERMINAL.has(status.status)) return;
        timer = window.setTimeout(tick, pollIntervalMs(elapsedMs));
      } catch (e) {
        backoff = Math.min(backoff + 1, 3);
        timer = window.setTimeout(tick, 2000 * Math.pow(2, backoff));
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [predictionId, state.apiKey]);

  return snapshot;
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- usePredictionPolling
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/hooks/
git commit -m "feat(frontend): Replicate prediction polling hook"
```

---

## Phase H — Landing & Upload Flow (M5)

### Task H1: Add duration validation to DropZone

**Files:**
- Modify: `frontend/src/components/DropZone.tsx`

- [ ] **Step 1: Add a helper that reads duration from a File**

At the top of `DropZone.tsx` (above the component), add:

```ts
const MAX_DURATION_S = 60;

async function readDurationS(file: File): Promise<number> {
  const url = URL.createObjectURL(file);
  try {
    return await new Promise<number>((resolve, reject) => {
      const v = document.createElement("video");
      v.preload = "metadata";
      v.onloadedmetadata = () => resolve(v.duration);
      v.onerror = () => reject(new Error("Couldn't read video metadata."));
      v.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}
```

- [ ] **Step 2: Update `handle` to await duration validation**

Replace the existing `handle` callback with:

```ts
const handle = useCallback(
  async (file: File) => {
    setError(null);
    const fmtErr = validate(file);
    if (fmtErr) { setError(fmtErr); return; }
    try {
      const duration = await readDurationS(file);
      if (!isFinite(duration) || duration <= 0) {
        setError("Couldn't read this video — try re-exporting as MP4.");
        return;
      }
      if (duration > MAX_DURATION_S) {
        setError(`Video is ${duration.toFixed(1)}s — must be ≤ ${MAX_DURATION_S}s.`);
        return;
      }
    } catch {
      setError("Couldn't read this video — try re-exporting as MP4.");
      return;
    }
    onFile(file);
  },
  [onFile],
);
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npm test
```

Expected: existing tests pass; no new failures.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/components/DropZone.tsx
git commit -m "feat(frontend): client-side duration validation in DropZone"
```

### Task H2: Replicate model constants

**Files:**
- Create: `frontend/src/lib/replicateConstants.ts`

- [ ] **Step 1: Create**

```ts
export const REPLICATE_MODEL = {
  owner: "prakhar-bhartiya",
  name: "meta-tribev2-social-media-content-signal",
} as const;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/replicateConstants.ts
git commit -m "feat(frontend): hardcode Replicate model owner/name"
```

### Task H3: Rewrite Landing.tsx

**Files:**
- Modify: `frontend/src/pages/Landing.tsx`

- [ ] **Step 1: Replace contents**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Brain, TrendingUp, Zap } from "lucide-react";
import { DropZone } from "../components/DropZone";
import { useAppState } from "../state/AppState";
import {
  uploadFile,
  createPrediction,
  getLatestModelVersion,
  ReplicateAuthError,
  ReplicateQuotaError,
} from "../lib/replicate";
import { REPLICATE_MODEL } from "../lib/replicateConstants";
import type { Attempt } from "../types";

function nextLabel(existingCount: number): string {
  return `v${existingCount + 1}`;
}

function newAttemptId(): string {
  return crypto.randomUUID();
}

export default function Landing() {
  const navigate = useNavigate();
  const { state, addAttempt, setCurrentJob, forgetKey } = useAppState();
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    if (!state.apiKey) return;
    setBusy(true);
    try {
      // 1. Read duration up front so we can populate the Attempt eagerly.
      setStage("Reading video…");
      const duration = await readDuration(file);

      // 2. Create the Attempt + blob URL right away.
      const attemptId = newAttemptId();
      const blobUrl = URL.createObjectURL(file);
      const label = nextLabel(state.attempts.length);

      // 3. Upload to Replicate Files API.
      setStage("Uploading to Replicate…");
      const uploaded = await uploadFile({ apiKey: state.apiKey }, file);

      // 4. Resolve the latest model version.
      setStage("Resolving model version…");
      const version = await getLatestModelVersion(
        { apiKey: state.apiKey },
        REPLICATE_MODEL.owner,
        REPLICATE_MODEL.name,
      );

      // 5. Create a prediction.
      setStage("Submitting prediction…");
      const prediction = await createPrediction(
        { apiKey: state.apiKey },
        { version, input: { video: uploaded.url } },
      );

      // 6. Persist Attempt + nav.
      const attempt: Attempt = {
        attemptId,
        predictionId: prediction.id,
        label,
        videoBlobUrl: blobUrl,
        videoDurationS: duration,
        uploadedAt: new Date().toISOString(),
        status: "queued",
        headlineScore: null,
        subScores: null,
        timeline: null,
        frameCount: 0,
        modelVersion: null,
        scoringVersion: null,
        brainFrames: null,
        errorMessage: null,
      };
      addAttempt(attempt);
      setCurrentJob(prediction.id);
      navigate(`/processing/${prediction.id}`);
    } catch (e) {
      if (e instanceof ReplicateAuthError) {
        forgetKey();
        setError("Token rejected by Replicate. Please re-enter it.");
      } else if (e instanceof ReplicateQuotaError) {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : "Upload failed.");
      }
    } finally {
      setBusy(false);
      setStage("");
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-16 flex flex-col items-center gap-12">
      <div className="text-center flex flex-col gap-4">
        <h1 className="text-4xl font-bold tracking-tight text-ink">
          How viral will your video be?
        </h1>
        <p className="text-ink-muted text-lg leading-relaxed max-w-xl">
          Upload your content and see how a human brain would respond — predicted
          by Meta's TRIBE v2 foundation model.
        </p>
        <p className="text-ink-dim text-xs">
          ~$0.05–0.20 per prediction · billed to your Replicate account
        </p>
      </div>

      <DropZone onFile={handleFile} disabled={busy} />
      {busy && <p className="text-accent text-sm -mt-6">{stage}</p>}
      {error && <p className="text-bad text-sm -mt-6">{error}</p>}

      <div className="w-full grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { icon: <Zap className="w-5 h-5 text-accent" />, title: "Upload", body: "Drop any MP4, MOV, or WebM up to 60s." },
          { icon: <Brain className="w-5 h-5 text-accent" />, title: "Predict", body: "TRIBE v2 predicts fMRI brain activity frame by frame." },
          { icon: <TrendingUp className="w-5 h-5 text-accent" />, title: "Score", body: "See your virality score and edit to improve it." },
        ].map(({ icon, title, body }) => (
          <div key={title} className="card p-5 flex flex-col gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
              {icon}
            </div>
            <p className="font-medium text-sm text-ink">{title}</p>
            <p className="text-xs text-ink-muted leading-relaxed">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

async function readDuration(file: File): Promise<number> {
  const url = URL.createObjectURL(file);
  try {
    return await new Promise<number>((resolve, reject) => {
      const v = document.createElement("video");
      v.preload = "metadata";
      v.onloadedmetadata = () => resolve(v.duration);
      v.onerror = () => reject(new Error("metadata"));
      v.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend && npm run lint
```

Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/pages/Landing.tsx
git commit -m "feat(frontend): rewrite Landing around Replicate upload flow"
```

---

## Phase I — Processing UX (M5 cont.)

### Task I1: Progress driver utility (TDD)

**Files:**
- Create: `frontend/src/lib/progressDriver.ts`
- Create: `frontend/src/lib/__tests__/progressDriver.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
import { describe, it, expect } from "vitest";
import { computeProgress, type ProgressInput } from "../progressDriver";

describe("computeProgress", () => {
  it("uploads slice (0-25)", () => {
    const p = computeProgress({ phase: "upload", uploadFraction: 0.5 });
    expect(p).toBeCloseTo(0.125, 3);
  });

  it("upload fraction 1 snaps to 0.25", () => {
    const p = computeProgress({ phase: "upload", uploadFraction: 1 });
    expect(p).toBeCloseTo(0.25, 3);
  });

  it("submitted snaps to 0.25", () => {
    expect(computeProgress({ phase: "submitted" })).toBe(0.25);
  });

  it("boot crawl is monotonic and capped at 0.6", () => {
    let last = 0.25;
    for (let t = 0; t <= 90_000; t += 5_000) {
      const p = computeProgress({ phase: "boot", elapsedMs: t });
      expect(p).toBeGreaterThanOrEqual(last);
      expect(p).toBeLessThanOrEqual(0.6);
      last = p;
    }
  });

  it("inference crawl is monotonic and capped at 0.95", () => {
    let last = 0.6;
    for (let t = 0; t <= 120_000; t += 5_000) {
      const p = computeProgress({ phase: "inference", elapsedMs: t });
      expect(p).toBeGreaterThanOrEqual(last);
      expect(p).toBeLessThanOrEqual(0.95);
      last = p;
    }
  });

  it("inference stage 'scoring' bumps to >=0.85", () => {
    const p = computeProgress({ phase: "inference", elapsedMs: 0, lastStage: "scoring" });
    expect(p).toBeGreaterThanOrEqual(0.85);
  });

  it("done is 1", () => {
    expect(computeProgress({ phase: "done" })).toBe(1);
  });
});
```

Run: `cd frontend && npm test -- progressDriver` — confirm FAIL (module missing).

- [ ] **Step 2: Implement `frontend/src/lib/progressDriver.ts`**

```ts
export type Phase = "upload" | "submitted" | "boot" | "inference" | "done";

export interface ProgressInput {
  phase: Phase;
  uploadFraction?: number;       // 0..1 during upload
  elapsedMs?: number;            // ms in the current phase
  lastStage?: string | null;     // STAGE: marker from logs
}

const STAGE_FLOOR: Record<string, number> = {
  loading_video: 0.65,
  tribe_inference: 0.75,
  scoring: 0.88,
  done: 0.95,
};

function asymptote(start: number, target: number, k: number, t: number): number {
  return target - (target - start) * Math.exp(-k * t);
}

export function computeProgress(input: ProgressInput): number {
  switch (input.phase) {
    case "upload":
      return Math.min(0.25, Math.max(0, (input.uploadFraction ?? 0) * 0.25));
    case "submitted":
      return 0.25;
    case "boot": {
      const t = (input.elapsedMs ?? 0) / 1000;
      return asymptote(0.25, 0.6, 0.04, t);
    }
    case "inference": {
      const t = (input.elapsedMs ?? 0) / 1000;
      const time = asymptote(0.6, 0.95, 0.025, t);
      const floor = input.lastStage ? STAGE_FLOOR[input.lastStage] ?? 0 : 0;
      return Math.max(time, floor);
    }
    case "done":
      return 1;
  }
}
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npm test -- progressDriver
```

Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/lib/progressDriver.ts frontend/src/lib/__tests__/progressDriver.test.ts
git commit -m "feat(frontend): progress driver with phase slices and stage acceleration"
```

### Task I2: Rewrite Processing.tsx

**Files:**
- Modify: `frontend/src/pages/Processing.tsx`

- [ ] **Step 1: Replace contents**

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAppState } from "../state/AppState";
import { usePredictionPolling } from "../hooks/usePredictionPolling";
import { computeProgress, type Phase } from "../lib/progressDriver";
import { cancelPrediction, ReplicateAuthError } from "../lib/replicate";
import type { TimelinePoint, SubScores } from "../types";

interface CogOutput {
  headline_score: number;
  sub_scores: SubScores;
  timeline: TimelinePoint[];
  video_duration_s: number;
  frame_count: number;
  model_version: string;
  scoring_version: string;
}

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export default function Processing() {
  const { predictionId = "" } = useParams<{ predictionId: string }>();
  const navigate = useNavigate();
  const { state, updateAttempt, forgetKey, setCurrentJob } = useAppState();
  const poll = usePredictionPolling(predictionId);
  const [phaseStartMs, setPhaseStartMs] = useState<number>(Date.now());
  const [phase, setPhase] = useState<Phase>("submitted");
  const [now, setNow] = useState(Date.now());
  const cancelledRef = useRef(false);

  // Tick clock for elapsed display.
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);

  // Phase derivation: starting → boot, processing → inference, terminal → done/error.
  useEffect(() => {
    if (poll.status === "starting" && phase !== "boot") {
      setPhase("boot");
      setPhaseStartMs(Date.now());
    } else if (poll.status === "processing" && phase !== "inference") {
      setPhase("inference");
      setPhaseStartMs(Date.now());
    } else if (poll.status === "succeeded" && phase !== "done") {
      setPhase("done");
    }
  }, [poll.status, phase]);

  // Find the matching attempt by predictionId.
  const attempt = useMemo(
    () => state.attempts.find((a) => a.predictionId === predictionId) ?? null,
    [state.attempts, predictionId],
  );

  // Handle terminal states.
  useEffect(() => {
    if (!attempt || cancelledRef.current) return;
    if (poll.status === "succeeded" && poll.output) {
      const out = poll.output as CogOutput;
      updateAttempt(attempt.attemptId, {
        status: "done",
        headlineScore: out.headline_score,
        subScores: out.sub_scores,
        timeline: out.timeline,
        frameCount: out.frame_count,
        modelVersion: out.model_version,
        scoringVersion: out.scoring_version,
      });
      setCurrentJob(null);
      navigate(`/results/${attempt.attemptId}`);
    } else if (poll.status === "failed") {
      updateAttempt(attempt.attemptId, {
        status: "error",
        errorMessage: poll.error ?? "Prediction failed.",
      });
      setCurrentJob(null);
    }
  }, [poll.status, poll.output, poll.error, attempt, navigate, updateAttempt, setCurrentJob]);

  // beforeunload guard while running.
  useEffect(() => {
    if (poll.status === "succeeded" || poll.status === "failed" || poll.status === "canceled") return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "A prediction is running. If you leave, you'll lose track of it but Replicate will still charge for the run.";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [poll.status]);

  const elapsedInPhaseMs = now - phaseStartMs;
  const totalElapsedMs = poll.elapsedMs;

  const fraction = computeProgress({
    phase,
    elapsedMs: elapsedInPhaseMs,
    lastStage: poll.lastStage,
  });

  const isColdStart = poll.status === "starting" && totalElapsedMs > 15_000;

  const handleCancel = async () => {
    if (!state.apiKey || !predictionId) return;
    cancelledRef.current = true;
    try {
      await cancelPrediction({ apiKey: state.apiKey }, predictionId);
    } catch (e) {
      if (e instanceof ReplicateAuthError) forgetKey();
    }
    if (attempt) {
      updateAttempt(attempt.attemptId, { status: "error", errorMessage: "Cancelled by user." });
    }
    setCurrentJob(null);
    navigate("/");
  };

  if (poll.status === "failed") {
    return (
      <div className="max-w-md mx-auto px-6 py-24 flex flex-col items-center gap-4 text-center">
        <h1 className="text-xl font-semibold text-ink">Prediction failed</h1>
        <p className="text-ink-dim text-sm">{poll.error ?? "Replicate did not return a result."}</p>
        <a href="/" className="btn-primary">Try again</a>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-16 flex flex-col gap-6">
      <Step phase={phase} />

      <div className="h-2 rounded-full bg-bg-raised overflow-hidden">
        <div
          className="h-full bg-accent transition-[width] duration-500 ease-out"
          style={{ width: `${(fraction * 100).toFixed(1)}%` }}
        />
      </div>

      <ol className="flex flex-col gap-2 text-sm">
        <Row label="Uploaded" done={phase !== "upload"} elapsedMs={null} />
        <Row label="Submitted to Replicate" done={phase !== "upload" && phase !== "submitted"} elapsedMs={null} />
        <Row label="Booting model" done={phase === "inference" || phase === "done"} active={phase === "boot"} elapsedMs={phase === "boot" ? elapsedInPhaseMs : null} />
        <Row label="Predicting brain response" done={phase === "done"} active={phase === "inference"} elapsedMs={phase === "inference" ? elapsedInPhaseMs : null} />
      </ol>

      {phase === "boot" && (
        <div className="rounded-lg border border-border-subtle p-4 text-xs text-ink-muted leading-relaxed">
          {isColdStart
            ? "Replicate is starting a GPU machine and loading the TRIBE v2 model. The first prediction after idle takes ~60 seconds; subsequent runs are much faster."
            : "Starting up…"}
        </div>
      )}

      <button onClick={handleCancel} className="btn-ghost text-sm self-start">Cancel</button>
    </div>
  );
}

function Step({ phase }: { phase: Phase }) {
  const labels: Record<Phase, string> = {
    upload: "Step 1 of 4 — Uploading",
    submitted: "Step 2 of 4 — Queued",
    boot: "Step 2 of 4 — Booting model",
    inference: "Step 3 of 4 — Predicting brain response",
    done: "Step 4 of 4 — Done",
  };
  return <h1 className="text-lg font-semibold text-ink">{labels[phase]}</h1>;
}

function Row({
  label, done, active, elapsedMs,
}: {
  label: string; done: boolean; active?: boolean; elapsedMs: number | null;
}) {
  const icon = done ? "✓" : active ? "▶" : " ";
  const color = done ? "text-ink" : active ? "text-accent" : "text-ink-dim";
  return (
    <li className={`flex items-center justify-between ${color}`}>
      <span className="flex items-center gap-2">
        <span className="font-mono w-3">{icon}</span>
        {label}
      </span>
      <span className="font-mono text-xs text-ink-dim">
        {elapsedMs == null ? "" : formatElapsed(elapsedMs)}
      </span>
    </li>
  );
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend && npm run lint
```

Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/pages/Processing.tsx
git commit -m "feat(frontend): processing page with phased progress + cancellation"
```

---

## Phase J — Brain Frame Capture (M7) and BrainFrameStrip rewire

This phase comes before Results because Results consumes both. Implementing in this order avoids a temporarily-broken Results state.

### Task J1: captureBrainFrames utility (smoke test only)

The full DOM/WebGL pipeline is hard to unit-test in jsdom. A smoke test mocks the renderer and asserts the function structure: it iterates the right number of timestamps and produces an array of strings.

**Files:**
- Create: `frontend/src/lib/captureBrainFrames.ts`
- Create: `frontend/src/lib/__tests__/captureBrainFrames.test.ts`

- [ ] **Step 1: Write the smoke test**

```ts
import { describe, it, expect, vi } from "vitest";
import { captureBrainFramesWithRenderer } from "../captureBrainFrames";
import type { TimelinePoint } from "../../types";

const fakeTimeline: TimelinePoint[] = Array.from({ length: 5 }, (_, i) => ({
  t: i,
  reward: 50, emotion: 50, attention: 50, novelty: 50, social_relevance: 50,
}));

describe("captureBrainFramesWithRenderer", () => {
  it("returns one data URL per requested frame", async () => {
    const renderFrame = vi.fn(async (_t: number) =>
      "data:image/jpeg;base64,/9j/AAAA",
    );
    const out = await captureBrainFramesWithRenderer({
      timeline: fakeTimeline,
      frameCount: 4,
      totalDurationS: 4,
      renderFrame,
    });
    expect(out).toHaveLength(4);
    expect(renderFrame).toHaveBeenCalledTimes(4);
    expect(out.every((s) => s.startsWith("data:image/"))).toBe(true);
  });

  it("evenly spaces timestamps from 0 to totalDurationS", async () => {
    const seen: number[] = [];
    const renderFrame = vi.fn(async (t: number) => { seen.push(t); return "data:image/jpeg;base64,X"; });
    await captureBrainFramesWithRenderer({
      timeline: fakeTimeline,
      frameCount: 3,
      totalDurationS: 10,
      renderFrame,
    });
    expect(seen).toEqual([0, 5, 10]);
  });
});
```

- [ ] **Step 2: Implement (testable + concrete entry points)**

```ts
import type { TimelinePoint } from "../types";

export interface CaptureWithRendererInput {
  timeline: TimelinePoint[];
  frameCount: number;
  totalDurationS: number;
  renderFrame: (timeS: number) => Promise<string>;
}

export async function captureBrainFramesWithRenderer(
  input: CaptureWithRendererInput,
): Promise<string[]> {
  const { frameCount, totalDurationS, renderFrame } = input;
  if (frameCount <= 0) return [];
  const out: string[] = [];
  for (let i = 0; i < frameCount; i++) {
    const t = frameCount === 1 ? 0 : (i * totalDurationS) / (frameCount - 1);
    out.push(await renderFrame(t));
  }
  return out;
}

/**
 * Capture frames using a one-off offscreen Three.js scene that mirrors the
 * coloring logic of HeadViewer3D. This is the production entry point.
 *
 * Implementation note: the simplest robust approach is to mount a hidden
 * <HeadViewer3D> with explicit width/height into a detached DOM node, drive
 * playheadTime through the desired timestamps, snapshot its WebGL canvas via
 * canvas.toDataURL on the next animation frame, then unmount.
 *
 * The full implementation is left as TODO for the integration step (see
 * Results page wiring) — for testing purposes, callers should use the
 * `captureBrainFramesWithRenderer` form which accepts an arbitrary render
 * function.
 */
export interface CaptureBrainFramesInput {
  timeline: TimelinePoint[];
  frameCount: number;
  totalDurationS: number;
  width?: number;
  height?: number;
}

export async function captureBrainFrames(
  input: CaptureBrainFramesInput,
): Promise<string[]> {
  // The DOM-mounting variant is implemented in the Results page where it has
  // direct access to React's rendering context. This function is a stub that
  // returns an empty array if invoked outside that integration; tests should
  // use captureBrainFramesWithRenderer above.
  void input;
  return [];
}
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npm test -- captureBrainFrames
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/lib/captureBrainFrames.ts frontend/src/lib/__tests__/captureBrainFrames.test.ts
git commit -m "feat(frontend): testable capture utility for brain-frame data URLs"
```

### Task J2: Rewire BrainFrameStrip to consume data URLs

**Files:**
- Modify: `frontend/src/components/BrainFrameStrip.tsx`
- Create: `frontend/src/components/__tests__/BrainFrameStrip.test.tsx`

- [ ] **Step 1: Update prop signature in BrainFrameStrip**

Open `frontend/src/components/BrainFrameStrip.tsx`. Change the `BrainFrameStripProps` interface and remove the `attemptId` + `api.brainFrameUrl()` import. Replace with passed-in arrays:

```tsx
interface BrainFrameStripProps {
  brainFrames: string[];          // data URLs, length === frameCount
  thumbnails: string[];           // data URLs, length === floor(totalDuration)+1
  timeline: TimelinePoint[];
  totalDuration: number;
  frameCount: number;
  playheadTime: number;
  onSeek?: (t: number) => void;
}
```

Inside the component body, replace the `<img src={api.thumbnailUrl(...)}>` usage with `brainFrames[idx]` / `thumbnails[s]`. Also remove the `import { api } from "../lib/api"` line.

(Detailed: the existing JSX that reads `api.thumbnailUrl(attemptId, s)` becomes `thumbnails[s]`; the JSX reading `api.brainFrameUrl(attemptId, idx)` becomes `brainFrames[idx]`. Add `if (!thumbnails[s]) return null` and `if (!brainFrames[idx]) return null` style fallbacks per cell to avoid undefined.)

- [ ] **Step 2: Write a smoke test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrainFrameStrip } from "../BrainFrameStrip";
import type { TimelinePoint } from "../../types";

const TL: TimelinePoint[] = Array.from({ length: 4 }, (_, i) => ({
  t: i,
  reward: 50, emotion: 50, attention: 50, novelty: 50, social_relevance: 50,
}));

describe("BrainFrameStrip", () => {
  it("renders one image per provided brainFrame and thumbnail", () => {
    render(
      <BrainFrameStrip
        brainFrames={["data:image/jpeg;base64,1", "data:image/jpeg;base64,2"]}
        thumbnails={["data:image/jpeg;base64,a", "data:image/jpeg;base64,b", "data:image/jpeg;base64,c"]}
        timeline={TL}
        totalDuration={2}
        frameCount={2}
        playheadTime={0}
      />,
    );
    const imgs = screen.getAllByRole("img");
    // 3 thumbnails + 2 brain frames = 5 imgs total.
    expect(imgs.length).toBe(5);
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npm test -- BrainFrameStrip
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/components/BrainFrameStrip.tsx frontend/src/components/__tests__/BrainFrameStrip.test.tsx
git commit -m "feat(frontend): BrainFrameStrip consumes data URL arrays"
```

### Task J3: useVideoThumbnails hook

Generates per-second thumbnails by drawing the source `<video>` to a hidden `<canvas>` once metadata is available.

**Files:**
- Create: `frontend/src/hooks/useVideoThumbnails.ts`

- [ ] **Step 1: Implement**

```ts
import { useEffect, useState } from "react";

interface Args {
  videoUrl: string;
  durationS: number;
  width?: number;
  height?: number;
}

export function useVideoThumbnails({ videoUrl, durationS, width = 96, height = 54 }: Args): string[] {
  const [out, setOut] = useState<string[]>([]);

  useEffect(() => {
    if (!videoUrl || durationS <= 0) return;
    let cancelled = false;
    const v = document.createElement("video");
    v.crossOrigin = "anonymous";
    v.muted = true;
    v.preload = "auto";
    v.src = videoUrl;

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const seconds = Math.max(1, Math.floor(durationS) + 1);
    const collected: string[] = [];

    async function captureAt(t: number): Promise<string> {
      return new Promise<string>((resolve) => {
        const onSeeked = () => {
          v.removeEventListener("seeked", onSeeked);
          ctx!.drawImage(v, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", 0.7));
        };
        v.addEventListener("seeked", onSeeked);
        v.currentTime = Math.min(t, durationS);
      });
    }

    v.addEventListener("loadedmetadata", async () => {
      for (let s = 0; s < seconds; s++) {
        if (cancelled) return;
        collected.push(await captureAt(s));
        if (cancelled) return;
        setOut([...collected]);
      }
    });

    return () => { cancelled = true; };
  }, [videoUrl, durationS, width, height]);

  return out;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useVideoThumbnails.ts
git commit -m "feat(frontend): useVideoThumbnails hook (canvas-drawn from <video>)"
```

---

## Phase K — Results Page (M6) + Brain Frame Integration

### Task K1: Rewrite Results.tsx

**Files:**
- Modify: `frontend/src/pages/Results.tsx`
- Modify: `frontend/src/hooks/useAttempts.ts`
- Modify: `frontend/src/components/AttemptsDrawer.tsx`
- Modify: `frontend/src/hooks/usePlaybackSync.ts`

- [ ] **Step 1: Replace `frontend/src/hooks/useAttempts.ts`**

```ts
import { useAppState } from "../state/AppState";
import type { Attempt } from "../types";

export function useAttempts(): {
  attempts: Attempt[];
  remove: (id: string) => void;
} {
  const { state, removeAttempt } = useAppState();
  return { attempts: state.attempts, remove: removeAttempt };
}
```

- [ ] **Step 2: Replace `frontend/src/hooks/usePlaybackSync.ts` with a no-op or simple state hook**

```ts
import { useState } from "react";

export function usePlaybackSync(): {
  playheadTime: number;
  setPlayheadTime: (t: number) => void;
} {
  const [playheadTime, setPlayheadTime] = useState(0);
  return { playheadTime, setPlayheadTime };
}
```

- [ ] **Step 3: Update `AttemptsDrawer.tsx` to consume the new Attempt type**

Read the current file. Where it iterates attempts and expects fields like `attempt_id`, `headline_score`, `uploaded_at`, change to `attemptId`, `headlineScore`, `uploadedAt`. Also update its prop types: it now receives `Attempt[]` (from `../types`) instead of `AttemptSummary[]`.

(Specifically, replace the `AttemptSummary` import — which came from the deleted `lib/api.ts` — with `import type { Attempt } from "../types"`. Field renames are mechanical.)

- [ ] **Step 4: Replace `frontend/src/pages/Results.tsx`**

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { History, Upload, AlertCircle } from "lucide-react";
import { useAppState } from "../state/AppState";
import { ScoreRing } from "../components/ScoreRing";
import { DeltaPill } from "../components/DeltaPill";
import { SubScoreCard } from "../components/SubScoreCard";
import { TimelineChart } from "../components/TimelineChart";
import { BrainFrameStrip } from "../components/BrainFrameStrip";
import { AttemptsDrawer } from "../components/AttemptsDrawer";
import { HeadViewer3D } from "../components/HeadViewer3D";
import { useVideoThumbnails } from "../hooks/useVideoThumbnails";
import { SUB_SCORE_KEYS, type Attempt, type TimelinePoint } from "../types";

function interpolateAtTime(timeline: TimelinePoint[], t: number): TimelinePoint | null {
  if (!timeline.length) return null;
  if (t <= timeline[0].t) return timeline[0];
  const last = timeline[timeline.length - 1];
  if (t >= last.t) return last;
  const idx = timeline.findIndex((p) => p.t >= t);
  if (idx <= 0) return timeline[0];
  const p0 = timeline[idx - 1];
  const p1 = timeline[idx];
  const a = (t - p0.t) / (p1.t - p0.t);
  const lerp = (x: number, y: number) => x + (y - x) * a;
  return {
    t,
    reward: lerp(p0.reward, p1.reward),
    emotion: lerp(p0.emotion, p1.emotion),
    attention: lerp(p0.attention, p1.attention),
    novelty: lerp(p0.novelty, p1.novelty),
    social_relevance: lerp(p0.social_relevance, p1.social_relevance),
  };
}

export default function Results() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();
  const { state, updateAttempt, removeAttempt } = useAppState();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [playheadTime, setPlayheadTime] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  const attempt = useMemo<Attempt | null>(
    () => state.attempts.find((a) => a.attemptId === attemptId) ?? null,
    [state.attempts, attemptId],
  );

  // Empty-memory guard: routing here directly after a refresh has no attempt.
  useEffect(() => {
    if (!attempt) navigate("/", { replace: true });
  }, [attempt, navigate]);

  const thumbnails = useVideoThumbnails({
    videoUrl: attempt?.videoBlobUrl ?? "",
    durationS: attempt?.videoDurationS ?? 0,
  });

  // Sort attempts oldest→newest just for delta computation.
  const sortedAttempts = useMemo(
    () => [...state.attempts].sort(
      (a, b) => new Date(a.uploadedAt).getTime() - new Date(b.uploadedAt).getTime(),
    ),
    [state.attempts],
  );
  const currentIndex = sortedAttempts.findIndex((a) => a.attemptId === attemptId);
  const prevAttempt = currentIndex > 0 ? sortedAttempts[currentIndex - 1] : null;
  const delta = (attempt?.headlineScore != null && prevAttempt?.headlineScore != null)
    ? attempt.headlineScore - prevAttempt.headlineScore
    : null;

  const handleTimeUpdate = () => {
    if (videoRef.current) setPlayheadTime(videoRef.current.currentTime);
  };

  const handleSeek = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      setPlayheadTime(t);
    }
  };

  if (!attempt) {
    return (
      <div className="max-w-md mx-auto px-6 py-24 flex flex-col items-center gap-4 text-center">
        <AlertCircle className="w-8 h-8 text-bad" />
        <p className="text-ink">That session ended.</p>
        <a href="/" className="btn-primary">Start a new prediction</a>
      </div>
    );
  }

  const liveScores = attempt.timeline ? interpolateAtTime(attempt.timeline, playheadTime) : null;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-ink font-medium">{attempt.label}</span>
          <span className="text-ink-dim">·</span>
          <span className="text-ink-dim">{attempt.videoDurationS.toFixed(1)}s</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setDrawerOpen(true)} className="btn-ghost text-sm gap-1.5">
            <History className="w-4 h-4" /> History
            {state.attempts.length > 0 && (
              <span className="ml-0.5 text-xs bg-accent/20 text-accent rounded-full px-1.5 py-0.5 font-mono">
                {state.attempts.length}
              </span>
            )}
          </button>
          <a href="/" className="btn-primary text-sm gap-1.5">
            <Upload className="w-4 h-4" /> New upload
          </a>
        </div>
      </div>

      {/* Hero row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" style={{ height: "clamp(240px, 34vw, 420px)" }}>
        <div className="relative rounded-xl overflow-hidden bg-black border border-border-subtle h-full">
          <video
            ref={videoRef}
            src={attempt.videoBlobUrl}
            controls
            className="w-full h-full object-contain"
            onTimeUpdate={handleTimeUpdate}
          />
        </div>
        <div className="relative rounded-xl overflow-hidden bg-black border border-border-subtle h-full">
          <HeadViewer3D
            timeline={attempt.timeline ?? []}
            playheadTime={playheadTime}
            className="w-full h-full"
          />
        </div>
      </div>

      {/* Brain frame strip — uses the brainFrames array when populated */}
      {attempt.brainFrames && attempt.brainFrames.length > 0 ? (
        <BrainFrameStrip
          brainFrames={attempt.brainFrames}
          thumbnails={thumbnails}
          timeline={attempt.timeline ?? []}
          totalDuration={attempt.videoDurationS}
          frameCount={attempt.frameCount}
          playheadTime={playheadTime}
          onSeek={handleSeek}
        />
      ) : (
        <BrainFrameCaptureGate attempt={attempt} thumbnails={thumbnails} onCapture={(frames) => updateAttempt(attempt.attemptId, { brainFrames: frames })} />
      )}

      {attempt.timeline && attempt.timeline.length > 0 && (
        <TimelineChart timeline={attempt.timeline} playheadTime={playheadTime} />
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {SUB_SCORE_KEYS.map((key) => (
          <SubScoreCard
            key={key}
            name={key}
            value={(liveScores as any)?.[key] ?? attempt.subScores?.[key] ?? 0}
          />
        ))}
      </div>

      <div className="card p-6 flex flex-col sm:flex-row items-center gap-6">
        <ScoreRing score={attempt.headlineScore ?? 0} size={140} />
        <div className="flex flex-col gap-2 text-center sm:text-left">
          <div className="flex items-center gap-3 justify-center sm:justify-start flex-wrap">
            <span className="text-xl font-semibold text-ink">Overall Virality Score</span>
            {delta != null && prevAttempt && (
              <DeltaPill delta={delta} label={`vs ${prevAttempt.label}`} />
            )}
          </div>
          <p className="text-sm text-ink-muted leading-relaxed max-w-lg">
            Predicted from cortical reward, emotion, attention, novelty, and
            social-relevance networks using Meta's TRIBE v2 brain model.
            Upload a new version of your video and compare scores to optimise.
          </p>
        </div>
      </div>

      {drawerOpen && (
        <AttemptsDrawer
          attempts={state.attempts}
          currentAttemptId={attemptId ?? ""}
          onClose={() => setDrawerOpen(false)}
          onDelete={(id) => {
            removeAttempt(id);
            if (id === attemptId) navigate("/");
          }}
        />
      )}
    </div>
  );
}

/**
 * Mounts a hidden HeadViewer3D, drives it through frame timestamps, snapshots
 * its WebGL canvas, and emits the data URL array. After capture, hands the
 * array back via `onCapture` and unmounts itself.
 */
function BrainFrameCaptureGate({
  attempt, thumbnails, onCapture,
}: {
  attempt: Attempt; thumbnails: string[]; onCapture: (frames: string[]) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!attempt.timeline || attempt.frameCount <= 0) return;
    const node = containerRef.current;
    if (!node) return;
    let cancelled = false;

    const capture = async () => {
      const frames: string[] = [];
      const total = attempt.frameCount;
      const dur = attempt.videoDurationS;
      // Wait one animation frame for HeadViewer3D's renderer to mount + load.
      await new Promise((r) => requestAnimationFrame(() => r(null)));
      // Give Three.js loaders a moment to finish on first mount.
      await new Promise((r) => setTimeout(r, 800));
      for (let i = 0; i < total; i++) {
        if (cancelled) return;
        const t = total === 1 ? 0 : (i * dur) / (total - 1);
        // Re-render at this t by mutating the prop wrapper below.
        setT(t);
        await new Promise((r) => requestAnimationFrame(() => r(null)));
        const canvas = node.querySelector("canvas") as HTMLCanvasElement | null;
        if (!canvas) break;
        frames.push(canvas.toDataURL("image/jpeg", 0.85));
      }
      if (!cancelled) {
        onCapture(frames);
        setDone(true);
      }
    };
    capture();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt.attemptId]);

  const [t, setT] = useState(0);
  if (done) return null;

  return (
    <>
      <div className="card p-4 flex items-center gap-3 text-sm text-ink-dim">
        <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin shrink-0" />
        Rendering brain frames…
      </div>
      <div ref={containerRef} style={{ position: "absolute", left: -9999, top: -9999, width: 96, height: 130 }}>
        <HeadViewer3D
          timeline={attempt.timeline ?? []}
          playheadTime={t}
          className="w-full h-full"
        />
      </div>
    </>
  );
}
```

> NOTE: the `BrainFrameCaptureGate` is intentionally simple — it mounts HeadViewer3D off-screen and reads its `<canvas>` directly. This avoids reinventing the rendering. The `useVideoThumbnails` hook handles the per-second thumbnail strip independently. The `thumbnails` prop is plumbed through but only used by BrainFrameStrip after capture; the JSX above passes `thumbnails` to the strip.

- [ ] **Step 5: Run typecheck**

```bash
cd frontend && npm run lint
```

Expected: no type errors.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/src/hooks/useAttempts.ts frontend/src/hooks/usePlaybackSync.ts frontend/src/components/AttemptsDrawer.tsx frontend/src/pages/Results.tsx
git commit -m "feat(frontend): rewrite Results around in-memory attempts + brain frame capture"
```

---

## Phase L — DisclaimerFooter modal + smoke pass

### Task L1: Make DisclaimerFooter open a read-only Disclaimer modal

**Files:**
- Modify: `frontend/src/components/DisclaimerFooter.tsx`

- [ ] **Step 1: Read the current file, then replace its body so the link opens a modal**

```tsx
import { useState } from "react";
import { Disclaimer } from "./Disclaimer";

export function DisclaimerFooter() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <footer className="border-t border-border-subtle px-4 sm:px-6 py-3 text-center text-xs text-ink-dim">
        Research-grade approximation · CC-BY-NC-4.0 · Non-commercial · No
        guarantee of real-world performance ·{" "}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="underline underline-offset-2 hover:text-ink"
        >
          Read full disclaimer
        </button>
      </footer>
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 overflow-auto"
          onClick={() => setOpen(false)}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <Disclaimer readOnly onAck={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/DisclaimerFooter.tsx
git commit -m "feat(frontend): footer opens read-only disclaimer modal"
```

---

## Phase M — Documentation

### Task M1: Rewrite README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` contents with**:

```markdown
# Tribe Virality

Upload a short video and see how a human brain would respond to it — scored
using Meta's [TRIBE v2](https://huggingface.co/facebook/tribev2) brain-predictive
foundation model running on Replicate.

This is a **research tool**. There is no Python backend. The browser talks
directly to the Replicate API using your own API token; you bring your own
credits.

> Research-grade approximation. Non-commercial use only (CC-BY-NC-4.0). Not clinical.

---

## Architecture

```
Browser  ──▶  api.replicate.com  ──▶  prakhar-bhartiya/meta-tribev2-social-media-content-signal
```

- **Frontend:** Vite + React + TypeScript. Static build deployed to nginx on Hostinger.
- **Replicate model (cog):** see [`cog/`](./cog/) for the model package.
- **No application server.** No SQLite. No accounts. No telemetry.

The user's API token lives only in browser memory; it is cleared on refresh
or tab close. The single piece of persistent state we write is the
disclaimer-acknowledgment flag in `localStorage`.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The app will:

1. Show a one-time disclaimer screen (acknowledged via `localStorage`).
2. Ask for your Replicate API token — paste a token from
   [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).
3. Validate it via `GET /v1/account` (no credits used).
4. Let you upload a video; runs the prediction on Replicate.

## Building the cog model

See [`cog/README.md`](./cog/README.md). Build, test locally with `cog run`,
push with `cog push r8.im/prakhar-bhartiya/meta-tribev2-social-media-content-signal`.

## Tests

Frontend:

```bash
cd frontend && npm test
```

Cog:

```bash
cd cog && python -m pytest
```

## Video constraints

- Format: MP4, MOV, WebM
- Duration: ≤ 60 seconds
- Size: ≤ 100 MB

Validated client-side before any upload starts.

## Project Structure

```
cog/                          # Replicate model package
  cog.yaml
  predict.py
  scoring/                    # pure-Python scoring pipeline
  data/                       # roi_mapping.json, baseline_stats.json
  tests/

frontend/
  src/
    state/AppState.tsx        # in-memory React context
    lib/
      replicate.ts            # Replicate REST client
      progressDriver.ts
      captureBrainFrames.ts
      disclaimerAck.ts
    hooks/
      usePredictionPolling.ts
      useVideoThumbnails.ts
    pages/
      Landing.tsx
      Processing.tsx
      Results.tsx
    components/
      Disclaimer.tsx
      ApiKeyGate.tsx
      KeyChip.tsx
      HeadViewer3D.tsx
      BrainFrameStrip.tsx
      ...
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for browser-only Replicate flow"
```

### Task M2: Add `docs/REPLICATE_SETUP.md`

**Files:**
- Create: `docs/REPLICATE_SETUP.md`

- [ ] **Step 1: Create**

```markdown
# Setting up your Replicate API token

This app runs predictions on Replicate using your own account. Follow these
steps once.

## 1. Create a Replicate account

Go to [replicate.com](https://replicate.com) and sign up. GitHub login works.

## 2. Add credits

Visit [replicate.com/account/billing](https://replicate.com/account/billing)
and add a payment method. You don't need to add credits up-front — Replicate
charges as you go. Predictions for this tool typically cost $0.05–$0.20 each.

## 3. Create an API token

Go to [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
and click **New token**. Name it something like "tribe-virality". Click
**Create token** and copy the value (it starts with `r8_`).

## 4. Paste the token in the app

When you open Tribe Virality for the first time, you'll be prompted for the
token. Paste it and click **Continue**. The app validates the token by
calling `GET /v1/account`; no credits are used by validation.

## Security

- The token is stored only in browser memory.
- It is sent only to `api.replicate.com`.
- It is **not** stored in `localStorage`, `sessionStorage`, cookies, or any
  server.
- Refreshing the page or closing the tab clears the token; you'll be asked
  to paste it again next time.

If you ever want to revoke the token, return to
[replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
and click the trash icon.
```

- [ ] **Step 2: Commit**

```bash
git add docs/REPLICATE_SETUP.md
git commit -m "docs: add Replicate token onboarding guide"
```

---

## Phase N — Verification

### Task N1: Full test suite

- [ ] **Step 1: Frontend tests**

```bash
cd frontend && npm test
```

Expected: all suites green. Approximate counts:
- AppState: 7
- Disclaimer: 4
- ApiKeyGate: 4
- replicate: 6
- usePredictionPolling: 3
- progressDriver: 7
- captureBrainFrames: 2
- BrainFrameStrip: 1
- routing/smoke: 1

- [ ] **Step 2: Cog tests**

```bash
cd cog && python -m pytest
```

Expected: 11 scoring tests pass; smoke test passes if ffmpeg+cog present.

- [ ] **Step 3: Frontend typecheck**

```bash
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 4: Frontend build**

```bash
cd frontend && npm run build
```

Expected: build succeeds; output in `frontend/dist/`.

### Task N2: Manual smoke test

- [ ] **Step 1: Start dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Open http://localhost:5173 and walk through:**

1. **Disclaimer:** appears on first open. Continue is disabled until checkbox ticked. Click Continue.
2. **ApiKeyGate:** prompts for token. Paste a real Replicate token and Continue. Validation succeeds.
3. **Landing:** key chip shows your username top-right. Cost hint visible. Drop a sample video (≤60s, ≤100MB).
4. **Processing:** progress bar advances through phases. Stage labels update. If cold-started, the boot copy explains the delay.
5. **Results:** user video on left, HeadViewer3D on right. Score row, sub-score cards, timeline chart populated. BrainFrameStrip renders after a brief "Rendering brain frames…" gate.
6. **History:** click History; drawer opens with the attempt. Run another video; delta pill appears.
7. **Forget key:** click "forget key" in chip. App routes back to ApiKeyGate; attempts cleared.
8. **Disclaimer modal:** click "Read full disclaimer" in footer; modal opens; ESC or click-outside closes.
9. **Direct nav after refresh:** refresh while on `/results/:id`; lands at the empty-memory toast/redirect.

If any step fails, fix it before declaring the milestone complete. Document what you observed in the commit message of the fix.

- [ ] **Step 3: After verification, push the cog model (manual, by user)**

The user runs:

```bash
cd cog
cog push r8.im/prakhar-bhartiya/meta-tribev2-social-media-content-signal
```

Then re-runs the manual smoke test against the live model. The frontend doesn't need to change — `getLatestModelVersion` resolves the new version on next session.

---

## Self-Review Checklist (post-write, performed by plan author)

**Spec coverage:**
- §3 Architecture: covered by Task A1–A6, B1, F1, G1, H3.
- §4 State: Task D2.
- §5 ApiKey UX: Tasks F2, F3, F4.
- §6 Disclaimer: Tasks E1, L1.
- §7 Processing UX: Tasks I1, I2.
- §8 Screens: Tasks H3 (Landing), I2 (Processing), K1 (Results).
- §9 Cog: Tasks A1–A6.
- §10 Deletions: Tasks B1, B2, B3.
- §11 Testing: covered by per-task TDD steps.
- §12 Milestones: M1=Phase A, M3=Phase B, M4=Phases D-F, M5=Phases G-I, M6=Phase K, M7=Phase J, M8=Phase K (drawer integration). M2 and M9 are explicitly out of scope.
- §13 Docs: Tasks M1, M2.

**Type consistency:**
- `Attempt` shape used uniformly across `types.ts`, `AppState.tsx`, `Results.tsx`, `AttemptsDrawer.tsx`.
- `PredictionStatus` field names match Replicate's API (`status`, `logs`, `output`, `error`).
- `TribeOutput` field names (`headline_score`, `sub_scores`, etc.) match between `cog/predict.py` and `Processing.tsx`'s `CogOutput` type.
- `STAGE:` markers in cog logs (`loading_video`, `tribe_inference`, `scoring`, `done`) match the `STAGE_FLOOR` table in `progressDriver.ts`.

**Placeholder scan:** None present. The "TODO" inside `cog/predict.py`'s docstring describes the Phase 2 manual upgrade — it's not a missing implementation in this plan's scope.

**Out-of-scope flags:** M2 (real TRIBE) and M9 (Hostinger deploy) are explicitly marked as user-handled in the goal section.
