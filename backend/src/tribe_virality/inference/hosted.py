"""Hosted inference backend (HF Inference Endpoint, Replicate, etc.).

Expects a service that accepts a multipart POST of the video and returns
a JSON payload `{"preds": [[...]]}` or a compact base64-encoded .npz.

This file defines a thin HTTP client; the actual endpoint adapter will depend
on the deployment. Left as a ready-to-extend stub.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import numpy as np

from ..config import settings
from ..scoring.rois import expected_n_vertices
from .backend import InferenceBackend, Segment


class HostedBackend:
    name = "hosted"

    def __init__(self, endpoint_url: str | None = None, api_token: str | None = None) -> None:
        self._url = endpoint_url or settings.hosted_endpoint_url
        self._token = api_token or settings.hosted_api_token
        if not self._url:
            raise RuntimeError(
                "TRIBE_HOSTED_ENDPOINT_URL must be set to use the 'hosted' backend."
            )

    async def predict_fmri(
        self, video_path: Path, duration_s: float
    ) -> tuple[np.ndarray, list[Segment]]:
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        timeout = httpx.Timeout(300.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            with video_path.open("rb") as f:
                files = {"video": (video_path.name, f, "video/mp4")}
                resp = await client.post(self._url, files=files, headers=headers)
            resp.raise_for_status()
            data = resp.content

        # Expected formats: .npz with key "preds", or JSON with key "preds".
        preds: np.ndarray
        try:
            with np.load(io.BytesIO(data)) as npz:
                preds = np.asarray(npz["preds"], dtype=np.float32)
        except Exception:
            import json as _json
            parsed = _json.loads(data.decode("utf-8"))
            preds = np.asarray(parsed["preds"], dtype=np.float32)

        if preds.ndim != 2:
            raise RuntimeError(f"Hosted endpoint returned preds with shape {preds.shape}")
        if preds.shape[1] != expected_n_vertices():
            raise RuntimeError(
                f"Hosted endpoint returned V={preds.shape[1]}; expected {expected_n_vertices()}."
            )
        t = preds.shape[0]
        segments = [Segment(start_s=0.0, end_s=float(duration_s), n_timesteps=t)]
        return preds, segments
