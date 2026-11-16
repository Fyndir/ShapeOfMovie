"""Data model and JSON (de)serialisation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

FORMAT_VERSION = 2


@dataclass
class MovieShape:
    """The colour signature of a movie: one colour every `step` seconds."""

    title: str
    colors: np.ndarray  # shape (n, 3), dtype uint8, in chronological order
    step: float | None = 1.0  # seconds between two samples (None if unknown)
    method: str = "mean"
    duration: float | None = None
    source: str | None = None
    meta: dict = field(default_factory=dict)  # free-form (e.g. Jellyfin ids)

    def __post_init__(self) -> None:
        self.colors = np.asarray(self.colors, dtype=np.uint8).reshape(-1, 3)

    def __len__(self) -> int:
        return len(self.colors)

    # --- JSON --------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": FORMAT_VERSION,
            "title": self.title,
            "method": self.method,
            "step": self.step,
            "duration": self.duration,
            "source": self.source,
            "meta": self.meta,
            "colors": [bytes(c).hex() for c in self.colors],
        }

    @classmethod
    def from_dict(cls, data: dict) -> MovieShape:
        if "frames" in data:  # format produced by the original 2020 version
            return cls._from_legacy(data)
        return cls(
            title=data["title"],
            colors=_hex_to_array(data["colors"]),
            step=data.get("step"),
            method=data.get("method", "mean"),
            duration=data.get("duration"),
            source=data.get("source"),
            meta=data.get("meta") or {},
        )

    @classmethod
    def _from_legacy(cls, data: dict) -> MovieShape:
        # Legacy files store unordered {"num": frame_index, "primalColor": hex}.
        frames = sorted(data["frames"], key=lambda f: int(f["num"]))
        return cls(
            title=data["titre"].strip(),
            colors=_hex_to_array([f["primalColor"] for f in frames]),
            step=None,
            method="legacy",
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> MovieShape:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _hex_to_array(values: list[str]) -> np.ndarray:
    if not values:
        return np.zeros((0, 3), dtype=np.uint8)
    return np.frombuffer(bytes.fromhex("".join(values)), dtype=np.uint8).reshape(-1, 3)
