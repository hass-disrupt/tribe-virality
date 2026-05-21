#!/usr/bin/env python3
"""Regenerate cog/data/roi_mapping.json from the Destrieux fsaverage5 atlas.

This is a BUILD-TIME generator, not part of the runtime image. The runtime
only reads the baked roi_mapping.json. The construct->parcel heuristic and
all pure logic live in scoring/atlas.py (unit-tested); this script is just the
nilearn IO shell.

Usage:
    pip install nilearn
    python cog/data/build_roi_mapping.py
    # review the diff, then commit roi_mapping.json

Assumes TRIBE's cortical output is the standard fsaverage5 vertex ordering:
left hemisphere [0:10242] then right hemisphere [10242:20484]. Verify this
against real TRIBE output with the landmark check described in METHODOLOGY.md
before trusting the scores.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make `scoring` importable when run as a standalone script from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.atlas import build_roi_mapping_dict  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / "roi_mapping.json"


def _decode(labels) -> list[str]:
    out = []
    for lb in labels:
        out.append(lb.decode() if isinstance(lb, (bytes, bytearray)) else str(lb))
    return out


def main() -> None:
    from nilearn import datasets

    atlas = datasets.fetch_atlas_surf_destrieux()
    label_names = _decode(atlas["labels"])
    mapping = build_roi_mapping_dict(
        label_names,
        atlas["map_left"],
        atlas["map_right"],
    )

    with OUT_PATH.open("w") as f:
        json.dump(mapping, f, indent=2)
        f.write("\n")

    total = mapping["n_vertices"]
    print(f"Wrote {OUT_PATH} ({total} vertices, atlas={mapping['atlas']})")
    for name, spec in mapping["buckets"].items():
        n = len(spec["vertex_indices"])
        print(f"  {name:<17} {n:>6} vertices ({100 * n / total:.1f}% of cortex)")


if __name__ == "__main__":
    main()
