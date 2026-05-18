# TRIBE Virality — Cog Model

This directory builds the Replicate model used by the Tribe Virality web app.
It packages real Meta TRIBE v2 inference plus the cortical-proxy scoring
pipeline.

## About TRIBE v2

TRIBE v2 ([facebook/tribev2](https://huggingface.co/facebook/tribev2)) is a
deep multimodal brain encoding model that predicts fMRI brain responses to
naturalistic video, audio, and text. Three pretrained towers feed a unified
Transformer that maps onto the cortical surface:

| Modality | Tower                                                               |
| -------- | ------------------------------------------------------------------- |
| Video    | [V-JEPA2](https://huggingface.co/facebook/vjepa2-vitg-fpc64-256)    |
| Audio    | [Wav2Vec-BERT](https://huggingface.co/facebook/w2v-bert-2.0)        |
| Language | [Llama 3.2-3B](https://huggingface.co/meta-llama/Llama-3.2-3B)      |

Output: fMRI predictions on the **fsaverage5** cortical mesh (~20k vertices)
for the average subject, shape `(n_timesteps, n_vertices)`.

License: CC-BY-NC-4.0 (Meta). See the [paper](https://ai.meta.com/research/publications/a-foundation-model-of-vision-audition-and-language-for-in-silico-neuroscience/)
for full details.

## How it works

```
video file
  -> tribev2.TribeModel.get_events_dataframe()   # extract video frames + transcribed speech (whisperx) + audio
  -> TribeModel.predict()                         # multimodal foundation-model fMRI prediction (T, V)
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
- `facebook/tribev2` (TRIBE Transformer + V-JEPA2 video tower + Wav2Vec-BERT audio tower + projection heads)
- `meta-llama/Llama-3.2-3B` (language tower, gated)
- whisperx weights (speech transcription, used to build the text input)
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
python -m pytest          # scoring tests + 1 predict smoke (skipped without GPU + cog image)
```

The full predict-path smoke test (`tests/test_predict_smoke.py`) needs
a GPU with the baked TRIBE weights, so it only runs inside the cog
image:

```bash
cog run python -c "from predict import Predictor; p = Predictor(); p.setup(); out = p.predict(video='/src/cog/tests/fixtures/sample.mp4'); print(out)"
```

## Scoring

> The scoring layer below is **our heuristic on top of TRIBE**. TRIBE itself
> predicts per-vertex fMRI signal; the "Virality Score" and the five sub-scores
> are not part of the model — they are a downstream mapping we apply to
> grouped vertex activations.

The headline virality score is a weighted combination of five cortical-proxy
sub-scores derived from TRIBE v2's fMRI predictions on the fsaverage5
cortical mesh:

| Sub-score        | Weight | Brain regions (cortical proxies)                     |
| ---------------- | ------ | ---------------------------------------------------- |
| Reward           | 30%    | Orbitofrontal cortex, ventromedial PFC               |
| Emotion          | 25%    | Anterior insula, anterior cingulate                  |
| Attention        | 20%    | Visual cortex, auditory cortex, intraparietal sulcus |
| Social Relevance | 15%    | Medial PFC, TPJ, precuneus                           |
| Novelty          | 10%    | Parahippocampal cortex, posterior cingulate          |

Each sub-score is the mean activation in its ROI, z-scored against a
synthesized baseline distribution and mapped through a sigmoid to 0–100.
The function is deterministic — re-uploading the same file yields the
same score.

The exact ROI vertex ranges live in `data/roi_mapping.json`; the baseline
means and stds in `data/baseline_stats.json`. Weights are declared in
`scoring/constants.py` and must sum to 1.0.

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
