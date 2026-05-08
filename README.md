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
- **Thin nginx reverse-proxy** at `/replicate-api/*` → `https://api.replicate.com/*`. Required because Replicate's API does not allow direct browser CORS. The proxy is configuration-only — no application logic, no logging of credentials, no persistence.
- **No application server.** No SQLite. No accounts. No telemetry.

The user's API token lives only in browser memory and transits the nginx
proxy as a transparent `Authorization: Bearer …` header in flight; it is
never stored on disk or in logs. The single piece of persistent state we
write is the disclaimer-acknowledgment flag in `localStorage`.

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

See [`docs/REPLICATE_SETUP.md`](./docs/REPLICATE_SETUP.md) for a step-by-step
guide to creating your Replicate account and API token.

## Production deployment (Hostinger)

Build the static bundle:

```bash
cd frontend && npm install && npm run build
# output: frontend/dist/
```

Serve `frontend/dist/` from nginx with a single proxy rule for the Replicate
endpoints:

```nginx
server {
  listen 443 ssl http2;
  server_name your-domain.example;

  root /var/www/tribe-virality/dist;
  index index.html;

  # SPA fallback
  location / {
    try_files $uri /index.html;
  }

  # Transparent proxy to Replicate. Never log Authorization or request bodies.
  location /replicate-api/ {
    proxy_pass https://api.replicate.com/;
    proxy_set_header Host api.replicate.com;
    proxy_ssl_server_name on;

    # Stream uploads up to 100 MB.
    client_max_body_size 110m;
    proxy_request_buffering off;
    proxy_buffering off;

    # Strip our hop's logging of credentials.
    access_log off;
  }
}
```

The proxy adds zero application logic — it only forwards requests so the
browser's same-origin policy is satisfied. The user's API token is set as
the `Authorization` header by the browser and passes through untouched.

## Building the cog model

See [`cog/README.md`](./cog/README.md). Build, test locally with `cog run`,
push with:

```bash
cog push r8.im/prakhar-bhartiya/meta-tribev2-social-media-content-signal
```

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
      replicate.ts            # Replicate REST client (host-pinned)
      progressDriver.ts       # phased upload/boot/inference progress
      captureBrainFrames.ts   # offscreen WebGL capture utility
      disclaimerAck.ts        # versioned localStorage ack flag
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
      HeadViewer3D.tsx        # interactive 3D brain (Three.js)
      BrainFrameStrip.tsx
      ...
```

## Scoring

The virality score is a weighted combination of five cortical-proxy
sub-scores derived from TRIBE v2's fMRI predictions on the fsaverage5
cortical mesh:

| Sub-score | Weight | Brain regions (cortical proxies) |
|-----------|--------|----------------------------------|
| Reward | 30% | Orbitofrontal cortex, ventromedial PFC |
| Emotion | 25% | Anterior insula, anterior cingulate |
| Attention | 20% | Visual cortex, auditory cortex, intraparietal sulcus |
| Social Relevance | 15% | Medial PFC, TPJ, precuneus |
| Novelty | 10% | Parahippocampal cortex, posterior cingulate |

Scores are z-scored against a synthesized baseline distribution and mapped
through a sigmoid to 0–100. The function is deterministic — re-uploading the
same file yields the same score.
