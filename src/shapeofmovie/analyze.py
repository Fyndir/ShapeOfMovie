"""Video -> MovieShape pipeline."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from shapeofmovie import colors as color_methods
from shapeofmovie.extract import iter_frames, probe
from shapeofmovie.models import MovieShape

log = logging.getLogger(__name__)

# progress(done_samples, expected_samples or None)
ProgressFn = Callable[[int, int | None], None]


def title_from_source(source: str) -> str:
    stem = Path(source.split("?", 1)[0]).stem
    return stem.replace(".", " ").replace("_", " ").strip()


def analyze(
    source: str | Path,
    *,
    method: str = "mean",
    step: float = 1.0,
    title: str | None = None,
    sample_width: int = 160,
    progress: ProgressFn | None = None,
) -> MovieShape:
    """Sample `source` every `step` seconds and reduce each frame to one colour."""
    source = str(source)
    color_fn = color_methods.get(method)
    info = probe(source)
    log.info("analysing %s (%dx%d, %s s) method=%s step=%ss", source, info.width, info.height,
             f"{info.duration:.0f}" if info.duration else "?", method, step)  # fmt: skip
    started = time.perf_counter()
    expected = int(info.duration // step) + 1 if info.duration else None

    samples: list[np.ndarray] = []
    for frame in iter_frames(source, step=step, width=sample_width, info=info):
        samples.append(color_methods.to_uint8(color_fn(frame)))
        if progress:
            progress(len(samples), expected)

    if progress:
        progress(len(samples), len(samples))  # final call: 100 %
    elapsed = time.perf_counter() - started
    speed = f", {info.duration / elapsed:.1f}x realtime" if info.duration and elapsed else ""
    log.info("analysed %s: %d samples in %.1f s%s", source, len(samples), elapsed, speed)
    return MovieShape(
        title=title or title_from_source(source),
        colors=np.array(samples, dtype=np.uint8).reshape(-1, 3),
        step=step,
        method=method,
        duration=info.duration,
        source=source,
    )
