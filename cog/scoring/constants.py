"""Scoring constants: sub-score names, weights, and region counts."""

from __future__ import annotations


SUB_SCORE_NAMES = (
    "reward",
    "emotion",
    "attention",
    "novelty",
    "social_relevance",
)

# Headline virality weights. Must sum to 1.0.
WEIGHTS: dict[str, float] = {
    "reward": 0.30,
    "emotion": 0.25,
    "attention": 0.20,
    "social_relevance": 0.15,
    "novelty": 0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"
