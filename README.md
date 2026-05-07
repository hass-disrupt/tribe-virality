# Tribe Virality

Upload a short video and see how a human brain would respond to it — scored using Meta's [TRIBE v2](https://ai.meta.com/blog/tribe-v2-brain-predictive-foundation-model/) brain-predictive foundation model.

**Outputs:**
- Virality Score (0–100)
- Five cortical sub-scores: Reward, Emotion, Attention, Novelty, Social Relevance
- Synced brain-activity visualization playing alongside your video
- Brain Activity Timeline chart with per-signal curves
- Session history so you can re-upload edited versions and track improvement

> Research-grade approximation. Non-commercial use only (CC-BY-NC-4.0). Not clinical.

---

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node | 18+ |
| ffmpeg | any recent |

Install ffmpeg on macOS:
```bash
brew install ffmpeg
```

---

## Quick Start

### 1. Backend

```bash
cd backend

# Install Python deps
pip install -e ".[dev]"
pip install matplotlib imageio imageio-ffmpeg   # brain renderer

# Run with mock backend (no GPU needed)
TRIBE_BACKEND=mock TRIBE_DATA_DIR=./data uvicorn tribe_virality.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Inference Backends

Switch via the `TRIBE_BACKEND` environment variable:

| Value | Description |
|-------|-------------|
| `mock` | Synthetic fMRI — no GPU, instant results. Default for development. |
| `local` | Runs `facebook/tribev2` locally. Requires ~16 GB VRAM or Apple Silicon M3+. See [tribev2 repo](https://github.com/facebookresearch/tribev2). |
| `hosted` | Posts video to a remote endpoint (HF Inference Endpoint, Replicate). Set `TRIBE_HOSTED_ENDPOINT_URL` and optionally `TRIBE_HOSTED_API_TOKEN`. |

### Capability detection & banner

On boot, the backend probes:
- accelerator (`mps` / `cuda` / `cpu`)
- total memory
- `tribev2` install state
- HuggingFace auth state
- `bf16` / `fp16` support

It assigns a tier and the frontend renders a banner:

| Tier   | Meaning |
|--------|---------|
| green  | All checks pass — local inference active. |
| yellow | Runs but slow/risky (e.g. CPU only, or 12-16 GB unified memory). Banner explains. |
| red    | Cannot run locally — automatically falls back to `mock`. Banner shows reason (missing tribev2, no HF auth, < 12 GB, etc.). |

`GET /api/capabilities` returns the full state for inspection.

### Using the local backend (Apple Silicon / CUDA GPU)

> **Status (Apple Silicon):** the local-MPS path runs through to feature extraction but full live inference is blocked on tribev2 toolchain compatibility. See [docs/mps-status.md](docs/mps-status.md) for the open issues. For a working real-model demo on Apple Silicon, use the hosted backend.

```bash
# 1. Install tribev2 from upstream
pip install "tribev2 @ git+https://github.com/facebookresearch/tribev2.git"

# 2. Pre-stage whisperx with pinned compatible deps (Apple Silicon only)
uv tool install --python 3.12 --force whisperx \
  --with "torch<2.6" --with "torchaudio<2.6" \
  --with "pyannote.audio==3.3.2" --with matplotlib

# 3. Authenticate with HuggingFace + request access to meta-llama/Llama-3.2-3B
huggingface-cli login

# 4. Newer transformers required for AutoVideoProcessor
pip install -U "transformers>=4.55"

# 5. Start the backend
cd backend
TRIBE_BACKEND=local TRIBE_DATA_DIR=./data uvicorn tribe_virality.main:app --reload --port 8000
```

---

## Running Tests

```bash
cd backend
pytest tests/unit/ -v
```

11 unit tests covering the scoring pipeline (pure function, deterministic, weight-verified).

---

## Project Structure

```
backend/
  src/tribe_virality/
    main.py              # FastAPI app factory
    config.py            # Settings (env vars)
    db.py / models.py    # SQLite via SQLAlchemy
    routes/              # upload, jobs, attempts
    scoring/             # pipeline, ROI mapping, baseline stats
    inference/           # mock / local / hosted backends
    media/               # ffprobe, thumbnails, brain renderer
    data/                # roi_mapping.json, baseline_stats.json
  tests/

frontend/
  src/
    pages/               # Landing, Processing, Results
    components/          # DropZone, ScoreRing, SubScoreCard, VideoPair, TimelineChart, ...
    hooks/               # useJobPolling, usePlaybackSync, useAttempts
    lib/                 # api.ts, session.ts, cn.ts
```

---

## Video Constraints

- Format: MP4, MOV, WebM
- Duration: ≤ 60 seconds
- Size: ≤ 100 MB

---

## Scoring

The virality score is a weighted combination of five cortical-proxy sub-scores derived from TRIBE v2's fMRI predictions on the fsaverage5 cortical mesh:

| Sub-score | Weight | Brain regions (cortical proxies) |
|-----------|--------|----------------------------------|
| Reward | 30% | Orbitofrontal cortex, ventromedial PFC |
| Emotion | 25% | Anterior insula, anterior cingulate |
| Attention | 20% | Visual cortex, auditory cortex, intraparietal sulcus |
| Social Relevance | 15% | Medial PFC, TPJ, precuneus |
| Novelty | 10% | Parahippocampal cortex, posterior cingulate |

Scores are z-scored against a synthesized baseline distribution and mapped through a sigmoid to 0–100. The function is deterministic — re-uploading the same file yields the same score.
