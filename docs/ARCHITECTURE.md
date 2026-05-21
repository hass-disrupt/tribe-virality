# Architecture

```
Browser  ──▶  api.replicate.com  ──▶  prakhar-bhartiya/meta-tribev2-social-media-content-signal
```

- **Frontend:** Vite + React + TypeScript. Static build deployed to nginx.
- **Replicate model (cog):** see [`../cog/`](../cog/) for the model package.
- **Thin nginx reverse-proxy** at `/replicate-api/*` → `https://api.replicate.com/*`.
  Required because Replicate's API does not allow direct browser CORS. The
  proxy is configuration-only — no application logic, no logging of
  credentials, no persistence.
- **No application server.** No database. No accounts. No telemetry.

## Data flow

1. Browser collects the user's Replicate API token (held in React state only).
2. Token is validated against `GET /v1/account` — no credits used.
3. User uploads a video; browser POSTs to `/v1/files`, then creates a
   prediction at `/v1/predictions` with the file URL.
4. Browser polls `/v1/predictions/{id}` for status + logs. Stage markers
   (`STAGE:loading_model`, `STAGE:tribe_inference`, …) emitted by the cog
   predictor drive the progress bar.
5. On success, the prediction output (headline score, sub-scores, per-step
   timeline) is rendered in the Results page.

## What the model predicts

[TRIBE v2](https://huggingface.co/facebook/tribev2) is a multimodal foundation
model (V-JEPA2 video tower + Wav2Vec-BERT audio tower + Llama-3.2-3B language
tower, unified Transformer head) that predicts per-vertex fMRI activation on
the fsaverage5 cortical mesh (~20k vertices) for naturalistic video, audio,
and text. The cog predictor runs TRIBE and then maps grouped vertex
activations through our [scoring pipeline](../cog/README.md#scoring) to
produce the headline score and five sub-scores shown in the UI.

## Privacy

The user's API token lives only in browser memory and transits the nginx
proxy as a transparent `Authorization: Bearer …` header in flight; it is
never stored on disk or in logs. The single piece of persistent state we
write is the disclaimer-acknowledgment flag in `localStorage`.

The video is uploaded directly to Replicate; it does not pass through any
server operated by the developer.

## Video constraints

- Format: MP4, MOV, WebM
- Duration: ≤ 60 seconds
- Size: ≤ 100 MB

Validated client-side before any upload starts.

## Project layout

```
cog/                          # Replicate model package
  cog.yaml
  predict.py
  METHODOLOGY.md              # scoring grounding, limitations, citations
  scoring/                    # pure-Python scoring pipeline (atlas ROIs, signs, baseline)
  data/                       # roi_mapping.json, baseline_stats.json + their generators
  tests/

dataset/                      # sample reference-clip predictions (the baseline corpus)

frontend/
  src/
    state/AppState.tsx        # in-memory React context
    lib/
      replicate.ts            # Replicate REST client (host-pinned)
      progressDriver.ts       # phased upload/boot/inference progress
      disclaimerAck.ts        # versioned localStorage ack flag
      replicateConstants.ts
      cn.ts
    hooks/
      usePredictionPolling.ts
      useVideoThumbnails.ts
    pages/
      Landing.tsx
      Processing.tsx
      Results.tsx
    components/
      Disclaimer.tsx · DisclaimerFooter.tsx
      ApiKeyGate.tsx · KeyChip.tsx
      TopBar.tsx · DropZone.tsx
      HeadViewer3D.tsx        # interactive 3D brain (Three.js)
      BrainFrameStrip.tsx · TimelineChart.tsx
      ScoreRing.tsx · SubScoreCard.tsx · DeltaPill.tsx
      AttemptsDrawer.tsx
      brain/colormap.ts
```

## Tests

```bash
cd frontend && npm test       # frontend unit tests
cd cog && python -m pytest    # scoring-pipeline tests (no GPU required)
```
