"""Pluggable inference backends."""

from .backend import InferenceBackend, Segment
from .factory import get_backend

__all__ = ["InferenceBackend", "Segment", "get_backend"]
