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
