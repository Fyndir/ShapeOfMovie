"""MovieShape -> image."""

from __future__ import annotations

from typing import Literal

import numpy as np
from PIL import Image

from shapeofmovie.models import MovieShape

Style = Literal["barcode", "vertical", "ring"]
STYLES: tuple[str, ...] = ("barcode", "vertical", "ring")


def render(
    shape: MovieShape,
    style: Style = "barcode",
    width: int = 1920,
    height: int = 1080,
    smooth: int = 0,
) -> Image.Image:
    """Draw the movie's colours.

    - barcode:  one vertical stripe per sample, time flows left to right
    - vertical: one horizontal line per sample, time flows top to bottom (original look)
    - ring:     time flows clockwise from 12 o'clock, `height` is ignored (square image)
    smooth: optional moving-average window (in samples) to soften flicker.
    """
    if len(shape) == 0:
        raise ValueError(f"'{shape.title}' has no colours to draw")
    strip = _smooth(shape.colors, smooth)

    if style == "barcode":
        return _stretch(strip[np.newaxis, :, :], width, height)
    if style == "vertical":
        return _stretch(strip[:, np.newaxis, :], width, height)
    if style == "ring":
        return _ring(strip, width)
    raise ValueError(f"unknown style '{style}', choose from {', '.join(STYLES)}")


def _smooth(colors: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(colors) < window:
        return colors
    kernel = np.ones(window) / window
    padded = np.pad(colors.astype(np.float64), ((window // 2, window - 1 - window // 2), (0, 0)), mode="edge")
    out = np.stack([np.convolve(padded[:, c], kernel, mode="valid") for c in range(3)], axis=1)
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def _stretch(pixels: np.ndarray, width: int, height: int) -> Image.Image:
    # BOX averages when shrinking (many samples -> few pixels) and repeats when enlarging.
    return Image.fromarray(np.ascontiguousarray(pixels), "RGB").resize((width, height), Image.Resampling.BOX)


def _ring(colors: np.ndarray, size: int, inner: float = 0.35, supersample: int = 2) -> Image.Image:
    final = size
    size *= supersample  # drawn larger then downscaled: anti-aliased edges
    c = (size - 1) / 2
    y, x = np.mgrid[0:size, 0:size]
    dx, dy = x - c, y - c
    radius = np.hypot(dx, dy) / c
    angle = (np.arctan2(dx, -dy) % (2 * np.pi)) / (2 * np.pi)  # 0 at 12 o'clock, clockwise
    idx = np.minimum((angle * len(colors)).astype(int), len(colors) - 1)
    img = np.zeros((size, size, 4), dtype=np.uint8)
    mask = (radius <= 1) & (radius >= inner)
    img[mask, :3] = colors[idx[mask]]
    img[mask, 3] = 255
    return Image.fromarray(img, "RGBA").resize((final, final), Image.Resampling.LANCZOS)
