# MPS-Optimized Local Inference Backend for TRIBE v2

**Status:** Draft
**Date:** 2026-05-07
**Author:** prakhar-bhartiya
**Target:** Replace the stub `local` backend in `tribe_virality.inference.local_mps` with a working, MPS-optimized implementation that runs `facebook/tribev2` locally on Apple Silicon, integrated with the existing FastAPI + React frontend.

---

## 1. Problem & Goals

The frontend is complete and currently serves results from a synthetic `MockBackend`. We need to wire up real TRIBE v2 inference on Apple Silicon (M3 Pro, 18 GB unified memory) so the system produces real fMRI predictions.

**Constraints:**
- Apple Silicon, 18 GB unified memory — TRIBE v2 (V-JEPA2 ViT-g + LLaMA 3.2-3B + Wav2Vec-BERT) is ~12-15 GB at fp32; we need fp16/bf16 to fit comfortably with headroom for the OS, browser, and dev tools.
- LLaMA 3.2 is a gated model; HuggingFace authentication and model access approval are required.
- Inference is slow (1-5 min per clip); UX must keep the user informed.
- Future production target: same code path will run on a user's local GPU (CUDA or MPS). Hardware capability detection must drive UX warnings up-front.

**Goals (this spec):**
1. Implement `LocalMPSBackend` so `TRIBE_BACKEND=local` works end-to-end.
2. Add a capability-detection module + `/api/capabilities` endpoint that informs the frontend of hardware suitability.
3. Surface sub-stage progress during the long inference call.
4. Gracefully fall back to mock when local cannot run, with a clear UI banner explaining why.
5. Produce a perf baseline table on M3 Pro for the sample videos.

**Non-goals:**
- CUDA performance tuning (handled when the codebase reaches production GPU rollout).
- Multi-GPU / distributed inference.
- Quantization beyond a flag-gated `optimum-quanto` int8 path. No accuracy validation harness for quantized output in v1; this is opt-in with a warning.
- Idle-unload-after-N-minutes policies.

---

## 2. Architecture Overview

The existing scaffolding stays intact; we extend it.

**Backend changes:**
```
backend/src/tribe_virality/
  capabilities.py              # NEW — detect device, memory, dtype, model fit
  inference/
    backend.py                 # extend Protocol — add ProgressCallback param
    local_mps.py               # rewrite — bf16, lazy load, 3-stage progress
    mock.py                    # extend — emit progress callbacks
    factory.py                 # extend — capability-aware fallback
  jobs/queue.py                # pass progress callback into backend
  config.py                    # add: tribe_quantize, tribe_cache_folder
  routes/
    health.py                  # NEW — /api/capabilities (split from /api/health)
  main.py                      # mount new health router

backend/scripts/
  smoke_local.py               # NEW — single-video smoke test for live model
  perf_baseline.py             # NEW — full-suite perf measurement

backend/tests/
  unit/test_capabilities.py    # NEW
  unit/test_factory_fallback.py # NEW
  unit/test_progress_callback.py # NEW
  integration/test_capabilities_endpoint.py # NEW
```

**Frontend changes:**
```
frontend/src/
  hooks/useCapabilities.ts            # NEW — fetch /api/capabilities once
  components/CapabilityBanner.tsx     # NEW — yellow/red banner
  pages/Landing.tsx                   # render banner above DropZone
  lib/api.ts                          # add api.capabilities()
```

**Docs:**
```
docs/perf-baseline.md          # NEW — measured latency table (regenerable)
README.md                      # update — local-backend setup, min specs
```

---

## 3. Capability Detection (`capabilities.py`)

Single source of truth, called from `/api/capabilities` and `factory.get_backend()`.

```python
@dataclass(frozen=True)
class Capabilities:
    # Hardware
    platform: str                 # "darwin" | "linux" | "windows"
    accelerator: str              # "mps" | "cuda" | "cpu"
    accelerator_name: str         # "Apple M3 Pro" | "NVIDIA RTX 4090" | ""
    total_memory_gb: float        # unified memory or VRAM
    available_memory_gb: float    # OS-reported free, best-effort
    bf16_supported: bool
    fp16_supported: bool

    # Software
    tribev2_installed: bool
    hf_authenticated: bool        # presence of token via HfFolder.get_token()

    # Decisions
    tier: Literal["green", "yellow", "red"]
    recommended_dtype: str        # "bf16" | "fp16" | "int8" | "none"
    fallback_reason: str | None   # populated when forced to mock
    can_run_local: bool
    warnings: list[str]           # human-readable strings rendered in UI banner
```

**Tier rules** (pure function over the hardware/software fields, evaluated top-to-bottom):

1. If `not tribev2_installed` OR `not hf_authenticated` → `red` with explanatory `fallback_reason`.
2. Else if `accelerator == "cpu"` AND `total_memory_gb < 24` → `red` (CPU-only on small RAM is unusable).
3. Else if `accelerator in ("mps", "cuda")` AND `total_memory_gb >= 16` → `green`, dtype `bf16`.
4. Else if `accelerator in ("mps", "cuda")` AND `total_memory_gb >= 12` → `yellow`, dtype `bf16` (or `int8` if `TRIBE_QUANTIZE=auto|int8`).
5. Else if `accelerator == "cpu"` AND `total_memory_gb >= 24` → `yellow` (will run, but expect ≥10× slower than MPS/CUDA).
6. Else → `red` with insufficient-memory reason.

**Detection sources:**
- MPS: `torch.backends.mps.is_available() and torch.backends.mps.is_built()`
- CUDA: `torch.cuda.is_available()`, `torch.cuda.get_device_properties(0).total_memory`
- Total memory (Apple unified): `psutil.virtual_memory().total`
- bf16 on MPS: probe via `torch.tensor([1.0], device="mps").to(torch.bfloat16)` once at boot, cached
- HF auth: `huggingface_hub.HfFolder.get_token() is not None`

**Caching:** computed once on first call; recomputable via `get_capabilities(refresh=True)` (used by `/api/capabilities?refresh=1`).

**`/api/capabilities` response shape:**

```json
{
  "tier": "green",
  "accelerator": "mps",
  "accelerator_name": "Apple M3 Pro",
  "total_memory_gb": 18.0,
  "recommended_dtype": "bf16",
  "active_backend": "local",
  "active_dtype": "bf16",
  "fallback_reason": null,
  "warnings": [],
  "can_run_local": true
}
```

When forced to mock:
```json
{
  "tier": "red",
  "accelerator": "cpu",
  "total_memory_gb": 8.0,
  "recommended_dtype": "none",
  "active_backend": "mock",
  "fallback_reason": "Insufficient memory: TRIBE v2 requires ≥12 GB; system has 8 GB.",
  "warnings": ["Running with synthetic mock backend — scores are illustrative."],
  "can_run_local": false
}
```

The frontend renders the banner directly from `warnings[]`. Backend owns the messaging.

**Tier minimum table:**

| Check                  | Green        | Yellow                              | Red |
|------------------------|--------------|-------------------------------------|-----|
| Accelerator            | MPS or CUDA  | MPS or CUDA (12-16 GB), or CPU ≥24 GB | CPU < 24 GB, or no accelerator with < 12 GB |
| Total RAM/VRAM         | ≥ 16 GB      | 12-16 GB (accelerated) / ≥ 24 GB (CPU) | < 12 GB (accelerated) / < 24 GB (CPU) |
| `tribev2` installed    | ✓            | ✓                                   | ✗   |
| HF auth (Llama 3.2)    | ✓            | ✓                                   | ✗   |
| Recommended dtype      | bf16         | bf16 + opt int8                     | — (forced mock) |

---

## 4. Inference Backend (`local_mps.py`)

```python
class LocalMPSBackend:
    name = "local"

    def __init__(self, capabilities: Capabilities, cache_folder: str = "./cache"):
        self._caps = capabilities
        self._cache_folder = cache_folder
        self._model: Optional[TribeModel] = None
        self._device = capabilities.accelerator        # "mps"|"cuda"|"cpu"
        self._dtype = self._resolve_dtype()            # torch.bfloat16 | torch.float16 | quanto-int8

    async def predict_fmri(
        self,
        video_path: Path,
        duration_s: float,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> tuple[np.ndarray, list[Segment]]:
        ...
```

**Progress sub-stages emitted via `progress_cb` (inner pct 0-100, mapped to outer 30-65 by the queue):**

| Inner % | stage_label                              | Trigger |
|---------|------------------------------------------|---------|
| 5       | `"Loading TRIBE model"`                  | First call only — skipped on subsequent |
| 30      | `"Transcribing & extracting features"`   | `get_events_dataframe()` (WhisperX + audio) |
| 60      | `"Predicting fMRI activity"`             | `model.predict()` |
| 95      | `"Validating output"`                    | shape/dtype checks |

**Lazy load (`_ensure_loaded`):**
1. Set `os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"` at module import (covers ops without MPS kernels).
2. `from tribev2.demo_utils import TribeModel` — note the `demo_utils` path; the existing stub uses the wrong top-level import.
3. `model = TribeModel.from_pretrained("facebook/tribev2", cache_folder=...)`. ~30-60s first time.
4. `model = model.to(self._device).to(self._dtype)` for bf16/fp16.
5. For int8: `from optimum.quanto import quantize, qint8, freeze; quantize(model, weights=qint8); freeze(model)` after device move.
6. `model.eval()`.

**Inference flow:**
```python
def _work():
    if progress_cb: progress_cb(5, "Loading TRIBE model")
    self._ensure_loaded()
    if progress_cb: progress_cb(30, "Transcribing & extracting features")
    events_df = self._model.get_events_dataframe(video_path=str(video_path))
    if progress_cb: progress_cb(60, "Predicting fMRI activity")
    with torch.inference_mode():
        preds, segments_raw = self._model.predict(events=events_df)
    if progress_cb: progress_cb(95, "Validating output")
    preds_np = np.asarray(preds, dtype=np.float32)
    if preds_np.ndim != 2:
        raise RuntimeError(f"Unexpected TRIBE preds shape {preds_np.shape}")
    if preds_np.shape[1] != expected_n_vertices():
        raise RuntimeError(
            f"TRIBE returned V={preds_np.shape[1]} vertices; ROI mapping expects "
            f"{expected_n_vertices()}. Update roi_mapping.json."
        )
    t = preds_np.shape[0]
    segments = [Segment(start_s=0.0, end_s=float(duration_s), n_timesteps=t)]
    if self._device == "mps":
        torch.mps.empty_cache()
    return preds_np, segments

return await asyncio.to_thread(_work)
```

**Memory policy:** lazy load + keep model in memory between jobs. Clear MPS scratch after each inference (`torch.mps.empty_cache()`); keep weights resident. First-load is 30-60s; unloading between jobs would impose that cost on every upload — bad UX. On OOM, defensive recovery: `del self._model; gc.collect(); torch.mps.empty_cache()`, set `_model=None`, surface a friendly error suggesting `TRIBE_QUANTIZE=int8` or hardware upgrade.

**MPS-specific niceties:**
- `torch.inference_mode()` (lighter than `torch.no_grad()`).
- bf16 outputs: coerce via `.float().cpu().numpy()` chain when extracting predictions.
- Set `os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"` early in module import.

**Error handling matrix:**

| Failure                                  | Handling |
|-----------------------------------------|----------|
| `tribev2` not importable                 | Factory catches at boot, returns mock. Detected pre-flight by capabilities. |
| HF auth error on `from_pretrained`       | Raise with friendly message: "Llama 3.2 access required. Run `huggingface-cli login` and request access at huggingface.co/meta-llama/Llama-3.2-3B" |
| `OutOfMemoryError` (or RuntimeError containing "out of memory") | Unload, set `_model=None`, raise with `TRIBE_QUANTIZE=int8` suggestion |
| Output shape mismatch                    | Raise with vertex-count diagnostic |

---

## 5. Wiring

### 5.1 Backend protocol (`inference/backend.py`)

```python
ProgressCallback = Callable[[int, str], None]   # (pct 0-100, label); thread-safe

class InferenceBackend(Protocol):
    name: str
    async def predict_fmri(
        self,
        video_path: Path,
        duration_s: float,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> tuple[np.ndarray, list[Segment]]: ...
```

`MockBackend` and `LocalMPSBackend` accept `progress_cb`; `HostedBackend` ignores for now.

### 5.2 Factory (`inference/factory.py`)

```python
@lru_cache(maxsize=1)
def get_backend() -> InferenceBackend:
    caps = get_capabilities()
    requested = settings.backend  # "mock"|"local"|"hosted"

    if requested == "local":
        if not caps.can_run_local:
            log.warning("Local backend requested but tier=%s; falling back to mock. Reason: %s",
                        caps.tier, caps.fallback_reason)
            return MockBackend()
        try:
            return LocalMPSBackend(caps)
        except Exception as exc:
            log.exception("LocalMPSBackend init failed; falling back to mock")
            _record_runtime_fallback(reason=str(exc))
            return MockBackend()

    if requested == "mock":   return MockBackend()
    if requested == "hosted": return HostedBackend()
    raise ValueError(f"Unknown TRIBE_BACKEND={requested!r}; use mock|local|hosted")
```

The factory may silently downgrade `local→mock` because `/api/capabilities` reports `active_backend` so the UI shows the user what is actually running.

### 5.3 Job queue (`jobs/queue.py`)

```python
def _make_progress_cb(self, job_id: str, base_pct: int = 30, span_pct: int = 35):
    def cb(inner_pct: int, label: str) -> None:
        outer = base_pct + int(span_pct * inner_pct / 100)
        self._update(job_id, progress=outer, stage_label=label)
    return cb

# In _run_job:
preds, _ = await backend.predict_fmri(
    spec.video_path,
    spec.duration_s,
    progress_cb=self._make_progress_cb(spec.job_id),
)
```

The callback runs on the inference thread (`asyncio.to_thread`); writes to the shared `_states` dict are coarse enough to be safe under the GIL without an explicit lock.

### 5.4 Frontend wiring

**`lib/api.ts`** — add:
```ts
export interface CapabilitiesResponse {
  tier: "green" | "yellow" | "red";
  accelerator: "mps" | "cuda" | "cpu";
  accelerator_name: string;
  total_memory_gb: number;
  recommended_dtype: string;
  active_backend: "mock" | "local" | "hosted";
  active_dtype: string;
  fallback_reason: string | null;
  warnings: string[];
  can_run_local: boolean;
}
api.capabilities = () => req<CapabilitiesResponse>("/api/capabilities");
```

**`hooks/useCapabilities.ts`** — fetch once via `useEffect`, no React Query dependency.

**`components/CapabilityBanner.tsx`** — render rules:
- `tier=green` → no banner.
- `tier=yellow` → yellow banner with `warnings[0]`, dismissible per session via `sessionStorage`.
- `tier=red` → red banner, non-dismissible, with `fallback_reason`; DropZone disabled.

**`pages/Landing.tsx`** — render banner above DropZone; pass `disabled={tier==="red"}` to DropZone.

---

## 6. Configuration (`config.py`)

New settings (all `TRIBE_`-prefixed):

| Setting              | Default   | Purpose |
|---------------------|-----------|---------|
| `tribe_cache_folder` | `./cache` | TribeModel cache location |
| `tribe_quantize`     | `none`    | `auto` \| `none` \| `int8` (controls quanto path) |
| `tribe_force_tier`   | `""`      | Test-only override: `green` \| `yellow` \| `red` |

Existing settings unchanged.

---

## 7. Testing Strategy

### 7.1 Unit tests (no hardware)

- `tests/unit/test_capabilities.py` — fakes `psutil`, `torch.backends.mps`, `huggingface_hub`. Covers green/yellow/red transitions, missing tribev2, missing HF auth, warnings populated.
- `tests/unit/test_factory_fallback.py` — local→mock fallback when `can_run_local=False`; local→mock when init raises; mock requested returns mock.
- `tests/unit/test_progress_callback.py` — MockBackend emits monotonically increasing progress; `progress_cb=None` works (backwards-compat).

Existing 11 scoring tests remain green; scoring pipeline is untouched.

### 7.2 Integration tests (FastAPI + httpx)

- `tests/integration/test_capabilities_endpoint.py` — asserts response shape; `TRIBE_FORCE_TIER=red` → mock served + banner-ready response.
- `tests/integration/test_upload_to_done_with_mock.py` — full upload → poll → attempt cycle confirms progress callback wiring doesn't break the queue.

### 7.3 Live smoke test (real model, MPS, sample video)

`backend/scripts/smoke_local.py` — not in pytest. Manual run:

1. Print capabilities; assert `tier != red`.
2. Construct `LocalMPSBackend`; time the lazy-load.
3. Run `predict_fmri` once on a sample video; capture progress events; time each stage.
4. Run scoring pipeline on output; print headline + sub-scores.
5. Run a SECOND time (no reload) and time it — should be ~`t_load_s` faster.
6. Print: process RSS before/after, peak `torch.mps.driver_allocated_memory()`.

### 7.4 End-to-end browser test

Manual checklist:
1. `cd backend && TRIBE_BACKEND=local uvicorn tribe_virality.main:app --reload`.
2. `cd frontend && npm run dev`.
3. Open localhost:5173, observe green banner with accelerator + active backend.
4. Upload `sample-videos/vid1.mp4`. Watch progress: queued → preprocessing → loading model → transcribing → predicting → scoring → done.
5. Land on Results with a real headline + timeline.
6. Repeat with `vid2.mp4` — confirm second run skips "Loading model".

Executed with Playwright MCP; screen states captured.

---

## 8. Performance Baseline

`backend/scripts/perf_baseline.py` — runs all sample videos and produces `docs/perf-baseline.md`.

**Per-video measurements:**
- `duration_s` — from ffprobe
- `size_mb` — file size
- `t_load_s` — first call only (excluded from per-video totals)
- `t_features_s` — `get_events_dataframe()` wall time
- `t_predict_s` — `model.predict()` wall time
- `t_score_s` — `score_preds()` wall time
- `t_total_s` — end-to-end excluding model load
- `mem_resident_gb` — `psutil.Process().memory_info().rss`
- `mem_mps_alloc_gb` — peak `torch.mps.driver_allocated_memory()`
- `headline_score` — sanity-check determinism between runs

**Run policy:** one warmup on `vid1.mp4` (records `t_load_s`, excluded from per-video totals); each subsequent video gets one timed run. Optional `--repeat N` for variance.

**Output:** `docs/perf-baseline.md` committed to repo, regenerable on demand. Baseline informs green/yellow tier thresholds.

---

## 9. Done Criteria

- `TRIBE_BACKEND=local` boots without errors on M3 Pro.
- `/api/capabilities` returns `tier=green`, `active_backend=local`, `accelerator=mps`.
- Uploading any sample video via the frontend completes end-to-end with real (non-mock-shaped) headline + sub-scores + timeline.
- Banner displays correctly in green/yellow/red simulations (use `TRIBE_FORCE_TIER` to test red+yellow paths without changing hardware).
- 11 existing scoring unit tests still pass; new unit + integration tests pass.
- `docs/perf-baseline.md` committed with measured numbers for the 5 sample videos.
- Brain renderer produces frames from real predictions (existing renderer + new predictions; non-fatal on failure).

---

## 10. Out of Scope

- CUDA-specific perf tuning.
- Quantization accuracy validation (int8 path is opt-in, not validated against fp32 reference in v1).
- Multi-GPU / distributed inference.
- Background model warmup at server boot (always lazy in v1; revisit if first-upload latency becomes a complaint).
- Idle-unload-after-N-minutes policy (not v1; add `IDLE_UNLOAD_AFTER_S` knob if memory pressure shows up in practice).
