"""Unit tests for capability detection tier rules."""

from __future__ import annotations

import pytest

from tribe_virality.capabilities import _decide_tier


def test_red_when_tribev2_missing():
    tier, dtype, reason, warns = _decide_tier(
        accelerator="mps",
        total_memory_gb=18.0,
        tribev2_installed=False,
        hf_authenticated=True,
    )
    assert tier == "red"
    assert dtype == "none"
    assert reason and "tribev2" in reason.lower()
    assert any("mock" in w.lower() for w in warns)


def test_red_when_hf_not_authenticated():
    tier, dtype, reason, warns = _decide_tier(
        accelerator="mps",
        total_memory_gb=18.0,
        tribev2_installed=True,
        hf_authenticated=False,
    )
    assert tier == "red"
    assert reason and "hugg" in reason.lower()


def test_green_on_18gb_mps():
    tier, dtype, reason, warns = _decide_tier(
        accelerator="mps",
        total_memory_gb=18.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "green"
    assert dtype == "bf16"
    assert reason is None
    assert warns == []


def test_green_on_16gb_mps_boundary():
    tier, _, _, _ = _decide_tier(
        accelerator="mps",
        total_memory_gb=16.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "green"


def test_yellow_on_14gb_mps():
    tier, dtype, reason, warns = _decide_tier(
        accelerator="mps",
        total_memory_gb=14.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "yellow"
    assert reason is None
    assert dtype in ("bf16", "int8")
    assert any("recommended" in w.lower() for w in warns)


def test_red_on_8gb_mps():
    tier, dtype, reason, warns = _decide_tier(
        accelerator="mps",
        total_memory_gb=8.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "red"
    assert reason and "12 gb" in reason.lower()


def test_red_on_8gb_cpu():
    tier, _, reason, _ = _decide_tier(
        accelerator="cpu",
        total_memory_gb=8.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "red"
    assert reason and "cpu" in reason.lower()


def test_yellow_on_32gb_cpu_only():
    tier, dtype, reason, warns = _decide_tier(
        accelerator="cpu",
        total_memory_gb=32.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "yellow"
    assert dtype == "bf16"
    assert any("cpu-only" in w.lower() or "slower" in w.lower() for w in warns)


def test_green_on_16gb_cuda():
    tier, _, _, _ = _decide_tier(
        accelerator="cuda",
        total_memory_gb=16.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "green"


def test_yellow_dtype_respects_quantize_setting(monkeypatch):
    from tribe_virality.config import settings as live_settings

    monkeypatch.setattr(live_settings, "tribe_quantize", "int8")
    tier, dtype, _, _ = _decide_tier(
        accelerator="mps",
        total_memory_gb=14.0,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "yellow"
    assert dtype == "int8"


@pytest.mark.parametrize("memory_gb", [11.9, 11.0, 5.0])
def test_red_below_12gb_threshold(memory_gb):
    tier, _, _, _ = _decide_tier(
        accelerator="mps",
        total_memory_gb=memory_gb,
        tribev2_installed=True,
        hf_authenticated=True,
    )
    assert tier == "red"
