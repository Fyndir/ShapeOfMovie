"""Strategies turning a frame into a single representative colour."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

ColorFn = Callable[[np.ndarray], np.ndarray]


def _pixels(frame: np.ndarray) -> np.ndarray:
    return frame.reshape(-1, 3).astype(np.float64)


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return c * 255.0


def mean(frame: np.ndarray) -> np.ndarray:
    """Plain average of the RGB values (what the original project did)."""
    return _pixels(frame).mean(axis=0)


def linear_mean(frame: np.ndarray) -> np.ndarray:
    """Average in linear light: closer to how the eye mixes colours, less muddy."""
    return _linear_to_srgb(_srgb_to_linear(_pixels(frame)).mean(axis=0))


def median(frame: np.ndarray) -> np.ndarray:
    """Per-channel median: robust to small, very bright or very dark areas."""
    return np.median(_pixels(frame), axis=0)


def dominant(frame: np.ndarray, k: int = 5) -> np.ndarray:
    """Centre of the largest k-means cluster (the colour covering most of the frame)."""
    try:
        from sklearn.cluster import KMeans
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("the 'dominant' method needs: pip install shapeofmovie[kmeans]") from exc
    px = _pixels(frame)
    k = min(k, len(np.unique(px, axis=0)))
    if k <= 1:
        return px[0]
    km = KMeans(n_clusters=k, n_init=1, random_state=0).fit(px)
    return km.cluster_centers_[np.bincount(km.labels_).argmax()]


METHODS: dict[str, ColorFn] = {
    "mean": mean,
    "linear": linear_mean,
    "median": median,
    "dominant": dominant,
}


def get(name: str) -> ColorFn:
    try:
        return METHODS[name]
    except KeyError:
        raise ValueError(f"unknown method '{name}', choose from {', '.join(METHODS)}") from None


def to_uint8(color: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(color), 0, 255).astype(np.uint8)
