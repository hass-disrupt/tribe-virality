"""Local MPS / CUDA backend using the `tribev2` package.

Runs Meta's TRIBE v2 model locally via the HuggingFace checkpoint
`facebook/tribev2`. Installation is separate from this repo:

    pip install "tribev2 @ git+https://github.com/facebookresearch/tribev2.git"
    huggingface-cli login   # required for gated LLaMA 3.2

Hardware notes:
- Requires ~8-12 GB free memory at bf16 (V-JEPA2 ViT-g + LLaMA 3.2-3B + Wav2Vec-BERT).
- On Apple Silicon (M2+), bf16 + MPS is the supported path.
- On CUDA, the same code path runs unchanged (auto-detected via Capabilities).
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

from ..capabilities import Capabilities
from ..scoring.rois import expected_n_vertices
from .backend import InferenceBackend, ProgressCallback, Segment

# MPS fallback for ops that don't have native kernels yet — set before torch import
# anywhere in the process to take effect. This module gets imported lazily by the
# factory, so we set it here as a safety net.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# tribev2 spawns `uvx whisperx ...` to transcribe audio. Without these env hints,
# uv defaults to the latest Python (3.14+) which resolves to torchaudio versions
# incompatible with the pyannote.audio version whisperx pins. Forcing 3.12 keeps
# uv on a known-good resolution path.
os.environ.setdefault("UV_PYTHON", "3.12")

log = logging.getLogger(__name__)


def _patch_tribev2_whisperx_compute_type() -> None:
    """tribev2 hardcodes whisperx `--compute_type float16`, which crashes on
    CPU/MPS (ctranslate2 only supports fp16 on CUDA). Apple Silicon falls back
    to CPU for whisperx; on CPU we must use `int8`. Monkey-patch the offending
    method to swap the arg before the subprocess is spawned.
    """
    try:
        from tribev2 import eventstransforms as _ets  # type: ignore[import-not-found]
    except ImportError:
        return

    cls = _ets.ExtractWordsFromAudio
    # The class attribute is a staticmethod descriptor; `cls.attr` returns the
    # underlying function directly when accessed on the class (Py 3.10+).
    original_func = cls._get_transcript_from_audio
    if getattr(original_func, "_mps_patched", False):
        return

    def patched(wav_filename, language):
        import subprocess as _sp

        real_run = _sp.run

        def run_with_int8(cmd, *args, **kwargs):
            try:
                idx = cmd.index("--compute_type")
                if idx + 1 < len(cmd):
                    cmd = list(cmd)
                    cmd[idx + 1] = "int8"
            except (ValueError, AttributeError):
                pass
            return real_run(cmd, *args, **kwargs)

        _sp.run = run_with_int8
        try:
            return original_func(wav_filename, language)
        finally:
            _sp.run = real_run

    patched._mps_patched = True  # type: ignore[attr-defined]
    cls._get_transcript_from_audio = staticmethod(patched)
    log.info("Patched tribev2 whisperx compute_type → int8 (CPU-compatible)")


_patch_tribev2_whisperx_compute_type()


def _resolve_torch_dtype(name: str):
    import torch

    return {
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
    }.get(name, torch.float32)


class LocalMPSBackend:
    """Wraps tribev2.demo_utils.TribeModel for local accelerated inference."""

    name = "local"

    def __init__(self, capabilities: Capabilities, cache_folder: str = "./cache") -> None:
        self._caps = capabilities
        self._cache_folder = cache_folder
        self._model = None
        self._device = capabilities.accelerator   # "mps" | "cuda" | "cpu"
        self._dtype_name = capabilities.recommended_dtype  # "bf16" | "fp16" | "int8"

    # ---- Lazy load ---------------------------------------------------------

    def _ensure_loaded(self, progress_cb: Optional[ProgressCallback] = None) -> None:
        if self._model is not None:
            return

        if progress_cb:
            progress_cb(5, "Loading TRIBE model")

        try:
            from tribev2.demo_utils import TribeModel  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "tribev2 package not installed. Install via "
                '`pip install "tribev2 @ git+https://github.com/facebookresearch/tribev2.git"` '
                "to enable the 'local' backend."
            ) from exc

        # TribeModel.from_pretrained accepts a `device` arg and internally calls
        # the underlying nn.Module's `.to(device)`. The wrapper itself is a
        # pydantic BaseModel — don't try to call .to(...) on it.
        #
        # The published `config.yaml` hardcodes `device: cuda` for each feature
        # extractor (text/audio/video). On Apple Silicon torch is built without
        # CUDA, so we must override these to "cpu". Note: extractors don't
        # support "mps" yet — heavy V-JEPA2/LLaMA layers use ops missing MPS
        # kernels. CPU is the safe lowest common denominator. The smaller brain
        # decoder still runs on MPS for the actual prediction step.
        extractor_device = "cpu"
        config_update = {
            # Text (LLaMA 3.2-3B)
            "data.text_feature.device": extractor_device,
            # Audio (Wav2Vec-BERT)
            "data.audio_feature.device": extractor_device,
            # Image (DINOv2-large)
            "data.image_feature.image.device": extractor_device,
            # Video (V-JEPA2 ViT-g)
            "data.video_feature.image.device": extractor_device,
        }

        try:
            t0 = time.perf_counter()
            tribe = TribeModel.from_pretrained(
                "facebook/tribev2",
                cache_folder=self._cache_folder,
                device=self._device,
                config_update=config_update,
            )
            log.info(
                "TribeModel.from_pretrained(device=%s, extractors=%s) took %.1fs",
                self._device,
                extractor_device,
                time.perf_counter() - t0,
            )
        except OSError as exc:
            msg = str(exc).lower()
            if "401" in msg or "403" in msg or "gated" in msg or "access" in msg:
                raise RuntimeError(
                    "Llama 3.2 access required. Run `huggingface-cli login` and request access "
                    "at https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct."
                ) from exc
            raise

        # Optional dtype cast on the inner nn.Module. We deliberately leave fp32
        # as the default for correctness — the brain decoder itself is small;
        # the heavy feature extractors run separately in get_events_dataframe.
        # bf16/int8 are opt-in via TRIBE_QUANTIZE for memory-pressured systems.
        try:
            import torch

            inner = getattr(tribe, "_model", None)
            if inner is None:
                raise RuntimeError("TribeModel._model not initialized after from_pretrained")

            if self._dtype_name == "int8":
                try:
                    from optimum.quanto import freeze, qint8, quantize  # type: ignore[import-not-found]

                    quantize(inner, weights=qint8)
                    freeze(inner)
                    log.info("Applied int8 quantization to inner brain decoder")
                except Exception as exc:
                    log.warning(
                        "optimum-quanto unavailable or failed (%s); keeping fp32", exc
                    )
                    self._dtype_name = "fp32"
            elif self._dtype_name in ("bf16", "fp16"):
                target_dtype = _resolve_torch_dtype(self._dtype_name)
                inner.to(target_dtype)
                log.info("Cast inner model to %s", self._dtype_name)
            # else: leave as fp32

            inner.eval()
        except Exception:
            log.exception(
                "Post-load setup failed (device=%s dtype=%s)",
                self._device,
                self._dtype_name,
            )
            raise

        self._model = tribe
        log.info(
            "LocalMPSBackend ready: device=%s dtype=%s",
            self._device,
            self._dtype_name,
        )

    # ---- Inference ---------------------------------------------------------

    async def predict_fmri(
        self,
        video_path: Path,
        duration_s: float,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> tuple[np.ndarray, list[Segment]]:
        def _work() -> tuple[np.ndarray, list[Segment]]:
            import torch

            try:
                self._ensure_loaded(progress_cb=progress_cb)
                assert self._model is not None

                if progress_cb:
                    progress_cb(30, "Transcribing & extracting features")
                events_df = self._model.get_events_dataframe(video_path=str(video_path))

                if progress_cb:
                    progress_cb(60, "Predicting fMRI activity")
                with torch.inference_mode():
                    preds, _segments_raw = self._model.predict(events=events_df)

                if progress_cb:
                    progress_cb(95, "Validating output")

                # Coerce torch tensor -> float32 numpy on CPU
                if hasattr(preds, "detach"):
                    preds_np = preds.detach().to(torch.float32).cpu().numpy()
                else:
                    preds_np = np.asarray(preds, dtype=np.float32)

                if preds_np.ndim != 2:
                    raise RuntimeError(f"Unexpected TRIBE preds shape {preds_np.shape}")
                if preds_np.shape[1] != expected_n_vertices():
                    raise RuntimeError(
                        f"TRIBE returned V={preds_np.shape[1]} vertices; "
                        f"ROI mapping expects {expected_n_vertices()}. "
                        "Update roi_mapping.json."
                    )

                t = preds_np.shape[0]
                segments = [Segment(start_s=0.0, end_s=float(duration_s), n_timesteps=t)]

                # Free MPS scratch buffers (keeps weights resident)
                if self._device == "mps":
                    try:
                        torch.mps.empty_cache()
                    except Exception:
                        pass
                elif self._device == "cuda":
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

                return preds_np, segments

            except RuntimeError as exc:
                # MPS/CUDA OOM error messages can vary — match defensively
                msg = str(exc).lower()
                if "out of memory" in msg or "oom" in msg:
                    log.exception("OOM during inference; unloading model")
                    self._model = None
                    gc.collect()
                    if self._device == "mps":
                        try:
                            torch.mps.empty_cache()
                        except Exception:
                            pass
                    elif self._device == "cuda":
                        try:
                            torch.cuda.empty_cache()
                        except Exception:
                            pass
                    raise RuntimeError(
                        "Out of memory during TRIBE v2 inference. Try setting "
                        "TRIBE_QUANTIZE=int8 or run on a system with more memory."
                    ) from exc
                raise

        return await asyncio.to_thread(_work)
