"""Select an inference backend based on env settings + detected capabilities."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from ..capabilities import get_capabilities
from ..config import settings
from .backend import InferenceBackend

log = logging.getLogger(__name__)


_runtime_fallback_reason: Optional[str] = None


def get_runtime_fallback_reason() -> Optional[str]:
    """If the requested backend was downgraded at runtime, the reason. Else None."""
    return _runtime_fallback_reason


def _record_runtime_fallback(reason: str) -> None:
    global _runtime_fallback_reason
    _runtime_fallback_reason = reason


def get_active_backend_name() -> str:
    """The name of the backend actually serving requests (post-fallback)."""
    return get_backend().name


@lru_cache(maxsize=1)
def get_backend() -> InferenceBackend:
    requested = settings.backend
    caps = get_capabilities()

    if requested == "local":
        from .mock import MockBackend  # imported lazily for test isolation

        if not caps.can_run_local:
            log.warning(
                "Local backend requested but tier=%s; falling back to mock. Reason: %s",
                caps.tier,
                caps.fallback_reason,
            )
            _record_runtime_fallback(
                caps.fallback_reason or f"Cannot run local backend (tier={caps.tier})"
            )
            return MockBackend()

        try:
            from .local_mps import LocalMPSBackend

            return LocalMPSBackend(caps, cache_folder=str(settings.tribe_cache_folder))
        except Exception as exc:
            log.exception("LocalMPSBackend init failed; falling back to mock")
            _record_runtime_fallback(f"LocalMPSBackend failed to initialize: {exc}")
            return MockBackend()

    if requested == "mock":
        from .mock import MockBackend

        return MockBackend()

    if requested == "hosted":
        from .hosted import HostedBackend

        return HostedBackend()

    raise ValueError(f"Unknown TRIBE_BACKEND={requested!r}; use mock|local|hosted")
