# MPS Local Inference — Status & Open Issues

**Last updated:** 2026-05-07
**Hardware tested:** Apple M3 Pro, 18 GB unified memory, macOS Darwin 25.4.0
**Status:** Foundation shipped; live inference blocked on tribev2 toolchain compatibility (see "Known issues").

---

## What works

- `tribe_virality.capabilities` correctly detects M3 Pro, MPS, bf16, 18 GB, tribev2 install state, HF auth.
- `/api/capabilities` returns the right tier (green when everything is available, red otherwise) and the frontend `CapabilityBanner` renders the right state.
- `MockBackend` works end-to-end with progress callbacks (verified via Playwright).
- Capability-aware factory cleanly falls back to mock when local can't initialize.
- 30 unit tests pass.

## What's blocked

Running real `facebook/tribev2` inference end-to-end on Apple Silicon. The pipeline gets through `TribeModel.from_pretrained → get_events_dataframe → text & audio extractors` but then needs to download the V-JEPA2 ViT-g checkpoint (~5 GB) and run it on CPU. We haven't seen a successful end-to-end inference yet.

---

## Known issues found while integrating tribev2 v0.1.0

Each of these required a workaround (already applied in `inference/local_mps.py` and `pyproject.toml`):

### 1. `TribeModel.to(device)` doesn't exist

**Why:** `TribeModel` is a `pydantic.BaseModel`, not a `torch.nn.Module`. `.to(...)` is intercepted by pydantic and returns `AttributeError`.

**Fix:** Pass `device="mps"` to `TribeModel.from_pretrained(...)` — the inner `nn.Module` is moved automatically by tribev2's loader.

### 2. `uvx whisperx` resolves Python 3.14 + incompatible torchaudio

`tribev2.eventstransforms.ExtractWordsFromAudio._get_transcript_from_audio` shells out to `uvx whisperx` for transcription. `uv` (without hints) defaults to the latest Python (3.14+) and the latest `torchaudio` (≥ 2.6), where `torchaudio.list_audio_backends()` was removed but `pyannote.audio` still calls it. Result: `AttributeError: module 'torchaudio' has no attribute 'list_audio_backends'`.

**Fix (applied):**
1. `os.environ.setdefault("UV_PYTHON", "3.12")` set at module import.
2. Pre-install whisperx as a `uv tool` with pinned compatible deps (one-time setup):
   ```
   uv tool install --python 3.12 --force whisperx \
     --with "torch<2.6" --with "torchaudio<2.6" \
     --with "pyannote.audio==3.3.2" --with matplotlib
   ```

### 3. Pyannote.audio missing `matplotlib`

`pyannote.audio.tasks.segmentation.mixins` imports matplotlib at module load. The whisperx tool env doesn't pull it transitively.

**Fix:** Add `--with matplotlib` to the `uv tool install` above.

### 4. Whisperx `--compute_type float16` fails on CPU

`tribev2.eventstransforms` hardcodes `compute_type="float16"`. ctranslate2 (whisperx's backend) only supports fp16 on CUDA. On CPU it errors: *"Requested float16 compute type, but the target device or backend do not support efficient float16 computation."*

**Fix (applied):** `inference/local_mps.py` monkey-patches `subprocess.run` to rewrite `--compute_type float16` → `int8` when whisperx is invoked.

### 5. Extractors hardcoded `device: cuda` in `config.yaml`

`facebook/tribev2`'s published `config.yaml` sets `device: cuda` for each feature extractor. On Apple Silicon (no CUDA), this raises `AssertionError: Torch not compiled with CUDA enabled` when extractors try `model.to("cuda")`.

**Fix (applied):** `LocalMPSBackend._ensure_loaded` passes `config_update={...}` to `TribeModel.from_pretrained` overriding all four extractor devices to `"cpu"`:

| Config key | Module |
|---|---|
| `data.text_feature.device` | LLaMA 3.2-3B |
| `data.audio_feature.device` | Wav2Vec-BERT |
| `data.image_feature.image.device` | DINOv2-large |
| `data.video_feature.image.device` | V-JEPA2 ViT-g |

This means feature extraction runs on CPU — slow (minutes per video), but at least correct. The brain decoder still runs on MPS.

### 6. `transformers >= 4.55` required for `AutoVideoProcessor`

`neuralset.extractors.video` imports `AutoVideoProcessor`, available only in transformers ≥ 4.55. Our pinned 4.51 didn't have it.

**Fix:** `pip install -U "transformers>=4.55"` (current: 5.8.0). Note: this triggers a `sentence-transformers` peer-dep warning; safe to ignore.

### 7. huggingface-hub 1.x removed `HfFolder.get_token()`

The transformers upgrade above pulled hf-hub 1.14, which moved token detection from `HfFolder.get_token()` to `huggingface_hub.get_token()`.

**Fix (applied):** `capabilities._detect_hf_auth` now tries `get_token()` first, falls back to `HfFolder.get_token()` for older installs.

### 8. tribev2 also installs an older torch (2.6.0)

Installing `tribev2` from source pins `torch==2.6.0`, downgrading whatever was previously installed. Acceptable, but note `torch.mps.driver_allocated_memory()` exists in 2.6 — our memory probes still work.

---

## What we haven't verified yet

- Whether V-JEPA2 ViT-g actually runs on CPU within a reasonable time on M3 Pro.
- Whether the brain decoder's MPS forward pass actually completes (we never reached `model.predict()` because feature extraction blocks on V-JEPA2 download + run).
- Whether MPS `bf16` cast on the brain decoder works end-to-end (suspect yes; the decoder is small).
- Whether `optimum-quanto` int8 path works on MPS.

---

## To finish this work

The cleanest path forward is **hosted inference** via the existing `HostedBackend` (already wired via `TRIBE_BACKEND=hosted`):

1. Stand up an HF Inference Endpoint, Modal, or Replicate deployment of `facebook/tribev2` on a CUDA box.
2. Set `TRIBE_HOSTED_ENDPOINT_URL` + `TRIBE_HOSTED_API_TOKEN` in `.env`.
3. The frontend banner already supports a "running on hosted endpoint" state.

If you want to keep pushing on local MPS:

1. Let the current smoke test finish (V-JEPA2 download takes ~10-20 min, then CPU inference per video another 10-30 min).
2. If it succeeds, capture `docs/perf-baseline.md` numbers — this is the perf truth.
3. If it fails, the issue is likely in `neuralset.extractors.video._HFVideoModel` or the V-JEPA2 model itself on CPU. Inspect the new traceback and patch as needed.

For production rollout of local inference on user GPUs, the right move is to upstream MPS support fixes to `facebook/tribev2`, not to keep monkey-patching downstream. Several of the issues above (CUDA-hardcoded YAML, broken `compute_type` default) deserve PRs.
