"""Hardware/software capability detection for the local inference backend.

Single source of truth for green/yellow/red tiering. Consumed by:
- inference.factory (decides whether to instantiate LocalMPSBackend or fall back to mock)
- routes.health (/api/capabilities endpoint, surfaced to the UI)
"""

from __future__ import annotations

import logging
import os
import platform as _platform
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

from .config import settings

log = logging.getLogger(__name__)


Tier = Literal["green", "yellow", "red"]
Accelerator = Literal["mps", "cuda", "cpu"]


@dataclass(frozen=True)
class Capabilities:
    # Hardware
    platform: str
    accelerator: Accelerator
    accelerator_name: str
    total_memory_gb: float
    available_memory_gb: float
    bf16_supported: bool
    fp16_supported: bool

    # Software
    tribev2_installed: bool
    hf_authenticated: bool

    # Decisions
    tier: Tier
    recommended_dtype: str
    fallback_reason: Optional[str]
    can_run_local: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = asdict(self)
        # tuple -> list for JSON
        d["warnings"] = list(self.warnings)
        return d


# ---- Detection helpers ------------------------------------------------------


def _detect_accelerator() -> tuple[Accelerator, str]:
    try:
        import torch  # noqa: F401
    except ImportError:
        return "cpu", ""

    import torch

    if torch.cuda.is_available():
        try:
            name = torch.cuda.get_device_name(0)
        except Exception:
            name = "CUDA device"
        return "cuda", name

    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        # Apple Silicon name
        return "mps", _apple_chip_name()

    return "cpu", _cpu_name()


def _apple_chip_name() -> str:
    try:
        import subprocess

        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
        return out or "Apple Silicon"
    except Exception:
        return "Apple Silicon"


def _cpu_name() -> str:
    return _platform.processor() or _platform.machine() or "CPU"


def _detect_total_memory_gb(accelerator: Accelerator) -> tuple[float, float]:
    """Return (total_gb, available_gb). For CUDA, returns VRAM."""
    if accelerator == "cuda":
        try:
            import torch

            props = torch.cuda.get_device_properties(0)
            total_gb = props.total_memory / 1024**3
            try:
                free, _ = torch.cuda.mem_get_info(0)
                avail_gb = free / 1024**3
            except Exception:
                avail_gb = total_gb
            return total_gb, avail_gb
        except Exception:
            return 0.0, 0.0

    # MPS or CPU: unified / system memory
    try:
        import psutil

        vm = psutil.virtual_memory()
        return vm.total / 1024**3, vm.available / 1024**3
    except Exception:
        return 0.0, 0.0


def _probe_dtypes(accelerator: Accelerator) -> tuple[bool, bool]:
    try:
        import torch
    except ImportError:
        return False, False

    bf16 = False
    fp16 = False
    try:
        if accelerator == "mps":
            t = torch.tensor([1.0], device="mps")
            try:
                _ = t.to(torch.bfloat16) + t.to(torch.bfloat16)
                bf16 = True
            except Exception:
                bf16 = False
            try:
                _ = t.to(torch.float16) + t.to(torch.float16)
                fp16 = True
            except Exception:
                fp16 = False
        elif accelerator == "cuda":
            bf16 = torch.cuda.is_bf16_supported()
            fp16 = True
        else:
            # CPU bf16 is supported on any modern x86/arm; fp16 less so
            bf16 = True
            fp16 = False
    except Exception:
        pass
    return bf16, fp16


def _detect_tribev2_installed() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("tribev2") is not None
    except Exception:
        return False


def _detect_hf_auth() -> bool:
    # Check env first (CI / explicit override)
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return True
    # huggingface-hub ≥ 0.20 exposes get_token(); older versions only had HfFolder
    try:
        from huggingface_hub import get_token

        if get_token() is not None:
            return True
    except ImportError:
        pass
    try:
        from huggingface_hub import HfFolder

        return HfFolder.get_token() is not None
    except Exception:
        return False


# ---- Tier decision ----------------------------------------------------------


def _decide_tier(
    *,
    accelerator: Accelerator,
    total_memory_gb: float,
    tribev2_installed: bool,
    hf_authenticated: bool,
) -> tuple[Tier, str, Optional[str], list[str]]:
    """Pure tier rule. Returns (tier, recommended_dtype, fallback_reason, warnings)."""
    warnings: list[str] = []

    if not tribev2_installed:
        return (
            "red",
            "none",
            "tribev2 package not installed. Install from "
            "https://github.com/facebookresearch/tribev2 to enable local inference.",
            [
                "Local inference unavailable: tribev2 package missing. "
                "Running with synthetic mock backend — scores are illustrative."
            ],
        )

    if not hf_authenticated:
        return (
            "red",
            "none",
            "HuggingFace not authenticated. Run `huggingface-cli login` and request access "
            "to meta-llama/Llama-3.2-3B before enabling the local backend.",
            [
                "Local inference unavailable: HuggingFace login required for Llama 3.2. "
                "Running with synthetic mock backend — scores are illustrative."
            ],
        )

    if accelerator == "cpu" and total_memory_gb < 24:
        return (
            "red",
            "none",
            f"CPU-only with {total_memory_gb:.1f} GB is below the minimum. "
            "Need MPS/CUDA (≥ 12 GB) or CPU (≥ 24 GB) to run locally.",
            ["No accelerator detected. Running with synthetic mock backend."],
        )

    if accelerator in ("mps", "cuda") and total_memory_gb >= 16:
        return ("green", "bf16", None, warnings)

    if accelerator in ("mps", "cuda") and total_memory_gb >= 12:
        warnings.append(
            f"{total_memory_gb:.0f} GB is below the recommended 16 GB. "
            "Inference may be slow or memory-tight; consider TRIBE_QUANTIZE=int8."
        )
        # Honour quantize setting
        dtype = "int8" if settings.tribe_quantize in ("auto", "int8") else "bf16"
        return ("yellow", dtype, None, warnings)

    if accelerator == "cpu" and total_memory_gb >= 24:
        warnings.append(
            "CPU-only execution detected. Expect ≥10× slower inference than MPS/CUDA."
        )
        return ("yellow", "bf16", None, warnings)

    return (
        "red",
        "none",
        f"Insufficient memory: TRIBE v2 requires ≥ 12 GB; system has {total_memory_gb:.1f} GB.",
        ["Insufficient memory. Running with synthetic mock backend."],
    )


# ---- Public API -------------------------------------------------------------


_cached: Optional[Capabilities] = None


def detect_capabilities() -> Capabilities:
    """Run all detection probes and decide the tier. Pure (no caching)."""
    # Test override (force-tier) takes precedence
    forced = settings.tribe_force_tier
    if forced in ("green", "yellow", "red"):
        platform_str = _platform.system().lower()
        accelerator, accel_name = _detect_accelerator()
        total_gb, avail_gb = _detect_total_memory_gb(accelerator)
        bf16, fp16 = _probe_dtypes(accelerator)
        # Synthesize fallback reasoning consistent with the forced tier
        if forced == "red":
            fallback_reason = "TRIBE_FORCE_TIER=red set (test override)."
            warnings = ["Forced red tier (test). Running with mock backend."]
            recommended = "none"
            can_run = False
        elif forced == "yellow":
            fallback_reason = None
            warnings = ["Forced yellow tier (test)."]
            recommended = "bf16"
            can_run = True
        else:  # green
            fallback_reason = None
            warnings = []
            recommended = "bf16"
            can_run = True
        return Capabilities(
            platform=platform_str,
            accelerator=accelerator,
            accelerator_name=accel_name,
            total_memory_gb=round(total_gb, 1),
            available_memory_gb=round(avail_gb, 1),
            bf16_supported=bf16,
            fp16_supported=fp16,
            tribev2_installed=_detect_tribev2_installed(),
            hf_authenticated=_detect_hf_auth(),
            tier=forced,
            recommended_dtype=recommended,
            fallback_reason=fallback_reason,
            can_run_local=can_run,
            warnings=tuple(warnings),
        )

    platform_str = _platform.system().lower()
    accelerator, accel_name = _detect_accelerator()
    total_gb, avail_gb = _detect_total_memory_gb(accelerator)
    bf16, fp16 = _probe_dtypes(accelerator)
    tribev2_installed = _detect_tribev2_installed()
    hf_authenticated = _detect_hf_auth()

    tier, recommended_dtype, fallback_reason, warnings = _decide_tier(
        accelerator=accelerator,
        total_memory_gb=total_gb,
        tribev2_installed=tribev2_installed,
        hf_authenticated=hf_authenticated,
    )

    can_run_local = tier in ("green", "yellow") and fallback_reason is None

    return Capabilities(
        platform=platform_str,
        accelerator=accelerator,
        accelerator_name=accel_name,
        total_memory_gb=round(total_gb, 1),
        available_memory_gb=round(avail_gb, 1),
        bf16_supported=bf16,
        fp16_supported=fp16,
        tribev2_installed=tribev2_installed,
        hf_authenticated=hf_authenticated,
        tier=tier,
        recommended_dtype=recommended_dtype,
        fallback_reason=fallback_reason,
        can_run_local=can_run_local,
        warnings=tuple(warnings),
    )


def get_capabilities(refresh: bool = False) -> Capabilities:
    """Cached capability detection. Call with refresh=True to recompute."""
    global _cached
    if _cached is None or refresh:
        _cached = detect_capabilities()
        log.info(
            "Capabilities detected: tier=%s accelerator=%s memory=%.1f GB tribev2=%s hf=%s",
            _cached.tier,
            _cached.accelerator,
            _cached.total_memory_gb,
            _cached.tribev2_installed,
            _cached.hf_authenticated,
        )
    return _cached
