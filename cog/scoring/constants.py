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
#
# These weights are a *heuristic prior*, not a fitted/validated parameter set
# (no engagement-labelled corpus exists to fit them; see METHODOLOGY.md). They
# lean toward reward/emotion because anticipatory-affect regions dominate the
# neuroforecasting literature (Genevsky & Knutson, PNAS 2020). Treat as tunable.
WEIGHTS: dict[str, float] = {
    "reward": 0.30,
    "emotion": 0.25,
    "attention": 0.20,
    "social_relevance": 0.15,
    "novelty": 0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# Direction of each construct's contribution, applied to the z-score *before*
# the sigmoid (score = sigmoid(sign * z) * 100). +1 = higher activation pushes
# the score up; -1 = higher activation pushes it down.
#
#   reward (+1)            : OFC/vmPFC value signal — higher → more engagement
#                            (reward/anticipatory affect; Genevsky & Knutson 2020;
#                            NAcc analogue, NAcc itself is subcortical & not
#                            exposed by the packaged model — see METHODOLOGY.md).
#   emotion (-1)           : anterior insula / salience — Genevsky & Knutson
#                            (PNAS 2020) found *decreased* anterior-insula
#                            activity forecasts MORE engagement, so higher
#                            activation lowers the score.
#   attention (+1)         : sensory/IPS engagement — heuristic prior.
#   novelty (+1)           : parahippocampal/PCC novelty — heuristic prior.
#   social_relevance (+1)  : mPFC/TPJ mentalizing — higher → more sharing
#                            (Falk et al. line of work); heuristic prior.
ROI_SIGN: dict[str, int] = {
    "reward": +1,
    "emotion": -1,
    "attention": +1,
    "novelty": +1,
    "social_relevance": +1,
}

assert set(ROI_SIGN) == set(SUB_SCORE_NAMES), "ROI_SIGN must cover every sub-score"
assert all(s in (-1, +1) for s in ROI_SIGN.values()), "ROI_SIGN values must be ±1"
