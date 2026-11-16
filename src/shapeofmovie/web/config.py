"""Settings, read from SOM_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    max_upload_mb: int = 20_000  # a 4K remux can weigh tens of GB
    workers: int = 1  # analyses running in parallel (each one keeps ffmpeg busy)
    default_method: str = "linear"
    default_step: float = 1.0

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get
        return cls(
            data_dir=Path(env("SOM_DATA_DIR", "data")),
            max_upload_mb=int(env("SOM_MAX_UPLOAD_MB", cls.max_upload_mb)),
            workers=int(env("SOM_WORKERS", cls.workers)),
            default_method=env("SOM_DEFAULT_METHOD", cls.default_method),
            default_step=float(env("SOM_DEFAULT_STEP", cls.default_step)),
        )

    @property
    def shapes_dir(self) -> Path:
        return self.data_dir / "shapes"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"
