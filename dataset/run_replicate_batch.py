#!/usr/bin/env python3
"""Batch-run every video in sample_raw_videos/ through the Replicate model and
save each prediction's full JSON to tribev2_output_jsons/<stem>.json.

The output JSON shape matches what cog/data/build_baseline_from_predictions.py
expects, so the typical workflow (run from anywhere) is:

    pip install replicate
    export REPLICATE_API_TOKEN=...
    python3 dataset/run_replicate_batch.py
    python3 cog/data/build_baseline_from_predictions.py dataset/tribev2_output_jsons

Idempotent: skips a video whose JSON already exists (pass --force to
re-run). Safe to interrupt and resume.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Defaults resolve next to this script (it lives in dataset/), so the command
# works regardless of the current working directory.
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RAW = SCRIPT_DIR / "sample_raw_videos"
DEFAULT_OUT = SCRIPT_DIR / "tribev2_output_jsons"
DEFAULT_MODEL = "prakhar-bhartiya/meta-tribev2-social-media-content-signal"

# Saved JSONs are sanitized (account-tying URLs/ids/logs stripped, see
# sanitize_predictions.py) so the committed sample dataset stays clean.
sys.path.insert(0, str(SCRIPT_DIR))
from sanitize_predictions import sanitize_payload  # noqa: E402

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
POLL_SECONDS = 5
RUNNING_STATES = {"starting", "processing"}


def _serialize(payload) -> dict:
    """Coax a Replicate prediction object into a plain JSON-able dict."""
    if hasattr(payload, "model_dump"):  # pydantic v2
        return payload.model_dump(mode="json")
    if hasattr(payload, "dict"):  # pydantic v1
        return payload.dict()
    return dict(payload)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="owner/name (latest version used)")
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing JSONs")
    args = ap.parse_args()

    try:
        import replicate
    except ImportError:
        raise SystemExit("Missing dependency: pip install replicate")
    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise SystemExit("Set REPLICATE_API_TOKEN in your environment")
    if not args.raw_dir.is_dir():
        raise SystemExit(f"Not a directory: {args.raw_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    videos = sorted(
        p for p in args.raw_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS
    )
    if not videos:
        raise SystemExit(f"No videos in {args.raw_dir}")

    # Resolve the latest model version once so every clip uses the same one.
    model = replicate.models.get(args.model)
    version = model.latest_version
    if version is None:
        raise SystemExit(f"Model {args.model} has no versions; push it first")

    print(f"Model:   {args.model}")
    print(f"Version: {version.id}")
    print(f"Input:   {args.raw_dir}  ({len(videos)} videos)")
    print(f"Output:  {args.out_dir}\n")

    started = time.time()
    n_ok = n_fail = n_skip = 0
    for video in videos:
        out_path = args.out_dir / f"{video.stem}.json"
        if out_path.exists() and not args.force:
            print(f"  skip {video.name} -> {out_path.name} already exists")
            n_skip += 1
            continue

        print(f"  run  {video.name}", flush=True)
        t0 = time.time()
        try:
            with video.open("rb") as fp:
                prediction = replicate.predictions.create(
                    version=version.id,
                    input={"video": fp},
                )
            while prediction.status in RUNNING_STATES:
                time.sleep(POLL_SECONDS)
                prediction.reload()
            elapsed = time.time() - t0
            if prediction.status != "succeeded":
                err = prediction.error or "(no error message)"
                print(f"       FAIL [{prediction.status}] in {elapsed:.0f}s: {err}")
                n_fail += 1
                continue

            raw = _serialize(prediction)
            output = raw.get("output") or {}
            if "timeline" not in output or "scoring_version" not in output:
                print(f"       WARN unexpected output shape — saving anyway")

            # Strip account-tying URLs/ids/logs before persisting.
            payload = sanitize_payload(raw, source=video.stem)
            with out_path.open("w") as f:
                json.dump(payload, f, indent=2, default=str)
                f.write("\n")
            print(f"       ok in {elapsed:.0f}s -> {out_path.name}")
            n_ok += 1
        except KeyboardInterrupt:
            print("\nInterrupted.")
            sys.exit(130)
        except Exception as e:
            print(f"       ERROR: {e}")
            n_fail += 1

    total = time.time() - started
    print()
    print(f"Done in {total / 60:.1f}m  (ok={n_ok}  fail={n_fail}  skip={n_skip})")
    if n_ok > 0 or n_skip > 0:
        print(
            f"Next:    python3 cog/data/build_baseline_from_predictions.py "
            f"{args.out_dir}"
        )


if __name__ == "__main__":
    main()
