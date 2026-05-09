# TRIBE Virality — Cog Model

This directory builds the Replicate model used by the Tribe Virality web app.
It packages real Meta TRIBE v2 inference plus the cortical-proxy scoring
pipeline.

## How it works

```
video file
  -> tribev2.TribeModel.get_events_dataframe()   # extract video + transcribed audio events
  -> TribeModel.predict()                         # foundation-model fMRI prediction (T, V)
  -> scoring.pipeline.score_preds()               # 5 cortical-proxy sub-scores + headline + timeline
```

## Prerequisites

You must have:

1. A HuggingFace account.
2. Approved access to **`meta-llama/Llama-3.2-3B`** (request at
   [huggingface.co/meta-llama/Llama-3.2-3B](https://huggingface.co/meta-llama/Llama-3.2-3B);
   typically approved within hours).
3. A HuggingFace access token with read scope. Create one at
   [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
4. A Replicate account with `cog` CLI installed (`brew install cog`).
5. Docker running locally for `cog build` / `cog push`.

## Build & push

The image bakes all model weights at build time so cold starts don't pay a
multi-GB download. The HuggingFace token is required only at build time
(it is **not** embedded in the final image).

```bash
cd cog

# One-time, if you haven't already authenticated to Replicate:
# cog login

# Cog passes secrets through to Docker BuildKit. Use the file-based form
# (--secret id=NAME,src=FILE). The env-based form (env=NAME) is fragile
# because cog's invocation of buildx doesn't always propagate shell env
# vars — symptom is a silently empty secret reaching the build container.

# Use a classic Read token (NOT a write or fine-grained token), created at
# huggingface.co/settings/tokens — Llama-3.2-3B is gated, write tokens
# often lack read-access to gated repos.

echo -n "hf_yourReadTokenHere" > /tmp/hf_token
wc -c /tmp/hf_token   # should print ~37 — confirms the token is present

cog push \
  --secret id=HUGGING_FACE_HUB_TOKEN,src=/tmp/hf_token \
  r8.im/prakhar-bhartiya/meta-tribev2-social-media-content-signal

rm /tmp/hf_token
```

The build downloads:
- `facebook/tribev2` (TRIBE weights + V-JEPA-2 video tower + projection heads)
- `meta-llama/Llama-3.2-3B` (language tower, gated)
- whisperx weights (audio transcription)
- fsaverage5 cortical-mesh assets

Total image size after baking: ~20–30 GB. Push takes 10–30 minutes the
first time depending on your upload bandwidth; subsequent pushes only ship
diffs.

## GPU

The model targets **Nvidia L40S** (48 GB VRAM, bf16 support). Configured
via `cog.yaml`'s `gpu: true` plus CUDA 12.1. You can override the GPU
type in the Replicate dashboard once the model is published.

## Local tests

The scoring pipeline tests do not require TRIBE itself and can be run
without GPU:

```bash
pip install -e ".[dev]"
python -m pytest          # 11 scoring tests + 1 predict smoke (smoke is skipped without cog/ffmpeg)
```

The full predict-path smoke test (`tests/test_predict_smoke.py`) was for
the Phase-1 synthetic predictor; in Phase 2 it stays skipped on local
runs because real TRIBE inference needs a GPU with the baked weights.
To exercise the full pipeline end-to-end inside the cog image:

```bash
cog run python -c "from predict import Predictor; p = Predictor(); p.setup(); out = p.predict(video='/src/cog/tests/fixtures/sample.mp4'); print(out)"
```

## Output schema

```python
class TribeOutput(BaseModel):
    headline_score: int                # 0–100
    sub_scores: dict[str, int]         # 5 keys: reward, emotion, attention, novelty, social_relevance
    timeline: list[dict[str, float]]   # one row per ~2 Hz fMRI step: {t, reward, emotion, attention, novelty, social_relevance}
    video_duration_s: float
    frame_count: int                   # = len(timeline)
    model_version: str                 # "tribev2-prod-v1" — bump when weights/scoring change
    scoring_version: str               # "1.0"
```

## Stage markers in logs

`predict()` emits machine-parseable lines (`STAGE:loading_model`,
`STAGE:loading_video`, `STAGE:tribe_inference`, `STAGE:scoring`,
`STAGE:done`) which the frontend parses to drive the progress bar. Keep
these markers stable across pushes.

## Bumping the model version

When you change anything that affects predictions (weight version,
scoring weights, baseline stats), bump `MODEL_VERSION` in `predict.py`
before `cog push`. The frontend stores this on each Attempt so users
can correlate scores back to a model revision.
