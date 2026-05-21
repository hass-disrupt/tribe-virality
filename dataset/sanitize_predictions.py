#!/usr/bin/env python3
"""Strip account-tying metadata from Replicate prediction JSONs.

A raw Replicate prediction carries the uploaded-video URL (a signed delivery
token or auth-gated Files API URL), the prediction id + account URLs, the
model/version, and a large `logs` blob. None are credentials, but they tie the
sample data to your account and bloat the files. This keeps only what the
baseline aggregation needs plus light provenance:

    {source, created_at, status, metrics, output}

`output` (timeline + sub_scores + scoring_version) is preserved, so
build_baseline_from_predictions.py still works on the sanitized files.

Usage:
    python3 dataset/sanitize_predictions.py dataset/tribev2_output_jsons
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Fields kept from the raw prediction; everything else (id, input, urls, logs,
# model, version, started_at, completed_at, error, data_removed) is dropped.
_KEEP = ("created_at", "status", "metrics")


def sanitize_payload(payload: dict, source: str) -> dict:
    """Return a minimal, account-agnostic view of a prediction payload."""
    clean = {"source": source}
    for key in _KEEP:
        if key in payload:
            clean[key] = payload[key]
    clean["output"] = payload.get("output") or {}
    return clean


def _is_sanitized(payload: dict) -> bool:
    # Already-clean files have no `input`/`urls`/`logs` and carry `source`.
    return "source" in payload and not any(
        k in payload for k in ("input", "urls", "logs", "id")
    )


def main(json_dir: str) -> None:
    dir_path = Path(json_dir)
    if not dir_path.is_dir():
        raise SystemExit(f"Not a directory: {dir_path}")
    files = sorted(p for p in dir_path.iterdir() if p.suffix == ".json")
    if not files:
        raise SystemExit(f"No JSON files in {dir_path}")

    before_total = after_total = 0
    n_done = n_skip = 0
    for f in files:
        before = f.stat().st_size
        payload = json.loads(f.read_text())
        if _is_sanitized(payload):
            print(f"  skip {f.name} (already sanitized)")
            n_skip += 1
            continue
        clean = sanitize_payload(payload, source=f.stem)
        if "timeline" not in clean["output"]:
            print(f"  WARN {f.name}: no output.timeline — kept anyway")
        f.write_text(json.dumps(clean, indent=2) + "\n")
        after = f.stat().st_size
        before_total += before
        after_total += after
        n_done += 1
        print(f"  ok   {f.name}  {before:,}B -> {after:,}B")

    print(
        f"\nSanitized {n_done} file(s), skipped {n_skip}."
        + (
            f" Size {before_total:,}B -> {after_total:,}B "
            f"({100 * (1 - after_total / before_total):.0f}% smaller)."
            if before_total
            else ""
        )
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: sanitize_predictions.py <dir-of-prediction-jsons>")
    main(sys.argv[1])
