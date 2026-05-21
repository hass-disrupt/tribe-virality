# Sample dataset & baseline corpus

The reference clips used to calibrate the empirical scoring baseline
(`cog/data/baseline_stats.json`), plus their TRIBE predictions.

```
dataset/
├── run_replicate_batch.py     # batch-runs clips through the Replicate model
├── sanitize_predictions.py    # strips account-tying URLs/ids/logs from JSONs
├── sample_raw_videos/         # raw .mp4 clips — GITIGNORED (size + copyright)
└── tribev2_output_jsons/      # committed: one sanitized prediction JSON per clip
```

## Privacy

The committed JSONs are **sanitized** — each is reduced to
`{source, created_at, status, metrics, output}`. The raw Replicate response's
upload URL (a signed delivery / auth-gated Files API link), prediction id +
account URLs, model/version, and verbose `logs` are stripped (none were
credentials, but they tie the data to the account and bloat the files ~3×).
`run_replicate_batch.py` applies this automatically on write; re-run
`python3 dataset/sanitize_predictions.py dataset/tribev2_output_jsons` if you
ever drop in raw responses.

## What's committed vs not

- **`tribev2_output_jsons/`** — committed. The actual "sample runs": each is a
  full Replicate prediction (timeline + sub-scores + metadata). Small,
  reproducible, no copyright concern.
- **`sample_raw_videos/`** — **not** committed. These are generic third-party
  clips; they're gitignored to keep the repo lean and avoid redistributing
  copyrighted media. Only `.gitkeep` is tracked so the path exists on clone.

## Regenerating the baseline corpus

```bash
# 1. Drop ~20-50 generic short clips into sample_raw_videos/
# 2. Run them through the deployed Replicate model:
pip install replicate
export REPLICATE_API_TOKEN=...
python3 dataset/run_replicate_batch.py        # writes tribev2_output_jsons/

# 3. Aggregate into cog/data/baseline_stats.json:
python3 cog/data/build_baseline_from_predictions.py dataset/tribev2_output_jsons
```

More clips ⇒ tighter σ estimates ⇒ better cross-video discrimination.

## ⚠️ Version caveat for `build_baseline_from_predictions.py`

That aggregator recovers TRIBE activations by **inverting the synthetic
baseline** (μ=0.5, σ=0.15) and only accepts predictions with
`scoring_version == 2.0`. The JSONs here were produced by the v2.0 model
*before* the empirical baseline shipped.

Once the deployed model uses an empirical baseline (v2.1+), its predictions can
**no longer** be inverted this way. To grow the corpus from then on, use
`cog/data/build_baseline_stats.py` instead — it reads raw ROI activations
in-image and is independent of the scoring version.
