"""Health and capability routes — surfaced to the frontend banner."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..capabilities import get_capabilities
from ..config import settings
from ..inference.factory import get_active_backend_name, get_runtime_fallback_reason


router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    """Lightweight liveness probe."""
    return {
        "ok": True,
        "backend": get_active_backend_name(),
        "requested_backend": settings.backend,
        "upload_max_bytes": settings.upload_max_bytes,
        "upload_max_duration_s": settings.upload_max_duration_s,
    }


@router.get("/capabilities")
async def capabilities(refresh: bool = Query(default=False)) -> dict:
    """Detected hardware/software capabilities + active backend.

    Frontend uses this to render the CapabilityBanner on the Landing page.
    """
    caps = get_capabilities(refresh=refresh)
    active = get_active_backend_name()
    runtime_reason = get_runtime_fallback_reason()

    # If the factory downgraded local→mock at runtime, prefer that reason.
    fallback_reason = runtime_reason or caps.fallback_reason

    # If we ended up on mock (whether requested or fallback), surface a warning
    # so the user knows scores are illustrative.
    warnings = list(caps.warnings)
    if active == "mock" and settings.backend == "local" and not any(
        "mock backend" in w.lower() for w in warnings
    ):
        warnings.insert(
            0,
            "Local inference unavailable — running with synthetic mock backend "
            "(scores are illustrative).",
        )

    return {
        "tier": caps.tier,
        "accelerator": caps.accelerator,
        "accelerator_name": caps.accelerator_name,
        "platform": caps.platform,
        "total_memory_gb": caps.total_memory_gb,
        "available_memory_gb": caps.available_memory_gb,
        "bf16_supported": caps.bf16_supported,
        "fp16_supported": caps.fp16_supported,
        "tribev2_installed": caps.tribev2_installed,
        "hf_authenticated": caps.hf_authenticated,
        "recommended_dtype": caps.recommended_dtype,
        "active_backend": active,
        "active_dtype": caps.recommended_dtype if active == "local" else "n/a",
        "requested_backend": settings.backend,
        "fallback_reason": fallback_reason,
        "can_run_local": caps.can_run_local,
        "warnings": warnings,
    }
