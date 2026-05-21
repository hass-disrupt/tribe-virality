"""Destrieux (aparc.a2009s) -> construct mapping.

Pure, dependency-light logic shared by ``data/build_roi_mapping.py`` (which
fetches the atlas via nilearn at build time) and the test-suite. Importing this
module does NOT import nilearn — the runtime image only ever reads the baked
``data/roi_mapping.json``.

The construct -> parcel table below is a *documented heuristic* mapping the
five virality constructs onto Destrieux cortical parcels. It is an approximation
(Destrieux has no clean mPFC/TPJ parcel; the best-validated reward signal, the
subcortical nucleus accumbens, is not exposed by the packaged TRIBE model).
See ``cog/METHODOLOGY.md`` for the rationale and citations.

Parcel names are matched as **case-sensitive substrings** of the Destrieux
label names returned by ``nilearn.datasets.fetch_atlas_surf_destrieux``.
"""

from __future__ import annotations

import numpy as np

from .constants import SUB_SCORE_NAMES

# construct -> list of Destrieux parcel-name fragments (substring match).
DESTRIEUX_CONSTRUCT_PARCELS: dict[str, list[str]] = {
    # Reward / value: orbitofrontal + ventromedial PFC (cortical proxy for the
    # subcortical NAcc reward signal that the packaged model does not expose).
    "reward": [
        "G_orbital",
        "S_orbital",
        "G_rectus",
        "S_suborbital",
        "G_subcallosal",
        "G_front_inf-Orbital",
    ],
    # Emotion / salience: anterior insula + anterior cingulate. Sign-inverted in
    # scoring (Genevsky & Knutson, PNAS 2020: anterior-insula DOWN -> engagement).
    "emotion": [
        "G_insular_short",
        "G_Ins_lg_and_S_cent_ins",
        "S_circular_insula_ant",
        "S_circular_insula_sup",
        "S_circular_insula_inf",
        "G_and_S_cingul-Ant",
        "G_and_S_cingul-Mid-Ant",
    ],
    # Attention: early visual + auditory + intraparietal sulcus.
    "attention": [
        "S_calcarine",
        "G_cuneus",
        "Pole_occipital",
        "G_occipital_sup",
        "G_occipital_middle",
        "G_and_S_occipital_inf",
        "S_oc_sup_and_transversal",
        "S_oc_middle_and_Lunatus",
        "G_oc-temp_med-Lingual",
        "S_oc-temp_med_and_Lingual",
        "G_temp_sup-G_T_transv",   # Heschl / primary auditory
        "G_temp_sup-Plan_tempo",
        "S_temporal_transverse",
        "S_intrapariet_and_P_trans",  # intraparietal sulcus
    ],
    # Novelty: parahippocampal + posterior cingulate.
    "novelty": [
        "G_oc-temp_med-Parahip",
        "S_collat_transv_ant",
        "G_cingul-Post-dorsal",
        "G_cingul-Post-ventral",
        "S_pericallosal",
    ],
    # Social relevance: medial PFC proxy + TPJ + precuneus (mentalizing).
    "social_relevance": [
        "G_front_sup",            # medial superior frontal ~ mPFC proxy
        "G_and_S_transv_frontopol",
        "G_pariet_inf-Angular",   # angular gyrus / TPJ
        "S_temporal_sup",         # posterior STS / TPJ
        "G_precuneus",
        "S_subparietal",
    ],
}

_CONSTRUCT_DESCRIPTIONS: dict[str, str] = {
    "reward": "Orbitofrontal + ventromedial PFC (Destrieux; cortical proxy for reward)",
    "emotion": "Anterior insula + anterior cingulate (Destrieux; sign-inverted)",
    "attention": "Early visual + auditory + intraparietal sulcus (Destrieux)",
    "novelty": "Parahippocampal + posterior cingulate (Destrieux)",
    "social_relevance": "Medial PFC proxy + TPJ/angular + precuneus (Destrieux)",
}


def build_roi_mapping_dict(
    label_names: list[str],
    labels_lh: np.ndarray,
    labels_rh: np.ndarray,
    construct_parcels: dict[str, list[str]] = DESTRIEUX_CONSTRUCT_PARCELS,
) -> dict:
    """Build a ``roi_mapping.json``-shaped dict from a Destrieux annotation.

    Vertex ordering is the standard fsaverage5 concatenation: left hemisphere
    first (indices ``0 .. len(labels_lh)-1``) then right hemisphere (offset by
    ``len(labels_lh)``). Each construct must resolve to >= 1 vertex.
    """
    labels_lh = np.asarray(labels_lh).ravel()
    labels_rh = np.asarray(labels_rh).ravel()
    n_lh = int(labels_lh.size)
    n_vertices = n_lh + int(labels_rh.size)

    buckets: dict[str, dict] = {}
    for name in SUB_SCORE_NAMES:
        if name not in construct_parcels:
            raise KeyError(f"Construct {name!r} missing from construct_parcels")
        fragments = construct_parcels[name]
        label_ids = [
            i
            for i, nm in enumerate(label_names)
            if any(frag in nm for frag in fragments)
        ]
        lh = np.nonzero(np.isin(labels_lh, label_ids))[0]
        rh = np.nonzero(np.isin(labels_rh, label_ids))[0] + n_lh
        verts = sorted(int(v) for v in np.concatenate([lh, rh]))
        if not verts:
            raise ValueError(
                f"Construct {name!r} matched 0 vertices "
                f"(parcel fragments {fragments!r} not found in atlas labels)"
            )
        buckets[name] = {
            "description": _CONSTRUCT_DESCRIPTIONS.get(name, name),
            "parcel_fragments": list(fragments),
            "vertex_indices": verts,
        }

    return {
        "_comment": (
            "Generated by cog/data/build_roi_mapping.py from the Destrieux "
            "(aparc.a2009s) surface atlas on fsaverage5 via nilearn. Vertex "
            "order = standard fsaverage5 lh[0:n] + rh[n:2n]. construct->parcel "
            "table is a documented heuristic; see cog/METHODOLOGY.md."
        ),
        "atlas": "destrieux_surface (aparc.a2009s) / fsaverage5",
        "n_vertices": n_vertices,
        "buckets": buckets,
    }
