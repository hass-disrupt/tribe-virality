"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


BackendName = Literal["mock", "local", "hosted"]
QuantizeMode = Literal["none", "auto", "int8"]
ForcedTier = Literal["", "green", "yellow", "red"]


class Settings(BaseSettings):
    """Top-level settings, read from env with TRIBE_ prefix."""

    model_config = SettingsConfigDict(env_prefix="TRIBE_", env_file=".env", extra="ignore")

    backend: BackendName = "mock"
    data_dir: Path = Path("./data")
    upload_max_bytes: int = 100 * 1024 * 1024  # 100 MB
    upload_max_duration_s: float = 60.0

    # Hosted backend (used only when backend == "hosted")
    hosted_endpoint_url: str = ""
    hosted_api_token: str = ""

    # Rendering
    brain_render_width: int = 640
    brain_render_height: int = 360
    brain_render_fps: int = 24

    # Local backend / TRIBE v2
    tribe_cache_folder: Path = Path("./cache")
    tribe_quantize: QuantizeMode = "none"
    # Test override only — forces capability tier regardless of detection.
    tribe_force_tier: ForcedTier = ""

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sessions.db"

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton
settings = Settings()
