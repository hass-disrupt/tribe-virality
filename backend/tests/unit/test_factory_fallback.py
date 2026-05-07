"""Unit tests for the capability-aware factory fallback logic."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _reset_factory_state():
    """Clear lru_cache + runtime fallback record between tests."""
    from tribe_virality.inference import factory

    factory.get_backend.cache_clear()
    factory._runtime_fallback_reason = None
    yield
    factory.get_backend.cache_clear()
    factory._runtime_fallback_reason = None


def _set_backend(monkeypatch, name: str):
    from tribe_virality.config import settings as live_settings

    monkeypatch.setattr(live_settings, "backend", name)


def test_mock_requested_returns_mock(monkeypatch):
    _set_backend(monkeypatch, "mock")
    from tribe_virality.inference import factory
    from tribe_virality.inference.mock import MockBackend

    b = factory.get_backend()
    assert isinstance(b, MockBackend)
    assert factory.get_runtime_fallback_reason() is None


def _make_caps(**overrides):
    from tribe_virality import capabilities as caps_mod

    base = dict(
        platform="darwin",
        accelerator="mps",
        accelerator_name="Apple M3 Pro",
        total_memory_gb=18.0,
        available_memory_gb=10.0,
        bf16_supported=True,
        fp16_supported=True,
        tribev2_installed=True,
        hf_authenticated=True,
        tier="green",
        recommended_dtype="bf16",
        fallback_reason=None,
        can_run_local=True,
        warnings=(),
    )
    base.update(overrides)
    return caps_mod.Capabilities(**base)


def test_local_requested_red_tier_falls_back_to_mock(monkeypatch):
    _set_backend(monkeypatch, "local")
    from tribe_virality.inference import factory
    from tribe_virality.inference.mock import MockBackend

    fake_caps = _make_caps(
        tier="red",
        recommended_dtype="none",
        tribev2_installed=False,
        fallback_reason="tribev2 missing",
        can_run_local=False,
        warnings=("synth backend",),
    )
    monkeypatch.setattr(factory, "get_capabilities", lambda refresh=False: fake_caps)

    b = factory.get_backend()
    assert isinstance(b, MockBackend)
    reason = factory.get_runtime_fallback_reason()
    assert reason and "tribev2" in reason


def test_local_init_failure_falls_back_to_mock(monkeypatch):
    _set_backend(monkeypatch, "local")
    from tribe_virality.inference import factory
    from tribe_virality.inference.mock import MockBackend

    fake_caps = _make_caps()
    monkeypatch.setattr(factory, "get_capabilities", lambda refresh=False: fake_caps)

    # Force LocalMPSBackend.__init__ to raise
    from tribe_virality.inference import local_mps as local_mod

    importlib.reload(local_mod)

    def _broken_init(self, *args, **kwargs):
        raise RuntimeError("simulated init failure")

    monkeypatch.setattr(local_mod.LocalMPSBackend, "__init__", _broken_init)

    b = factory.get_backend()
    assert isinstance(b, MockBackend)
    reason = factory.get_runtime_fallback_reason()
    assert reason and "simulated init failure" in reason
