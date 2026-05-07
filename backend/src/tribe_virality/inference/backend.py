"""Inference backend protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class Segment:
    """A temporal segment of the TRIBE output."""

    start_s: float
    end_s: float
    n_timesteps: int


# (inner_pct in [0,100], stage_label) -> None. Thread-safe (called from inference thread).
ProgressCallback = Callable[[int, str], None]


@runtime_checkable
class InferenceBackend(Protocol):
    """Predict fMRI response for a given video.

    Implementations must return:
      preds    : np.ndarray of shape (T, V), float
      segments : list[Segment] describing how T maps to time
    """

    name: str

    async def predict_fmri(
        self,
        video_path: Path,
        duration_s: float,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> tuple[np.ndarray, list[Segment]]: ...
