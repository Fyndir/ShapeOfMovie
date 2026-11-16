import json
from pathlib import Path

import numpy as np
import pytest

from shapeofmovie import MovieShape, analyze, render
from shapeofmovie.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize("method", ["mean", "linear", "median", "dominant"])
def test_analyze_recovers_colors(rgb_video, method):
    shape = analyze(rgb_video, method=method, step=1.0)
    assert shape.title == "Red Green Blue"
    assert len(shape) == 6
    expected = [[255, 0, 0]] * 2 + [[0, 128, 0]] * 2 + [[0, 0, 255]] * 2  # ffmpeg "green" is 008000
    # yuv420p round-trip is lossy: allow a small tolerance
    assert np.abs(shape.colors.astype(int) - expected).max() <= 12


def test_json_roundtrip(tmp_path):
    shape = MovieShape("Test", np.array([[1, 2, 3], [250, 128, 0]]), step=2.0, meta={"jellyfin_id": "x"})
    shape.save(tmp_path / "t.json")
    loaded = MovieShape.load(tmp_path / "t.json")
    assert loaded.title == "Test" and loaded.step == 2.0 and loaded.meta == {"jellyfin_id": "x"}
    np.testing.assert_array_equal(loaded.colors, shape.colors)


def test_examples_load():
    files = sorted(EXAMPLES.rglob("*.json"))
    assert len(files) == 10
    for f in files:
        shape = MovieShape.load(f)
        assert len(shape) > 1000 and shape.method in ("mean", "dominant")


def test_legacy_format_loads_in_order():
    legacy = Path(__file__).parent / "data" / "legacy.json"
    shape = MovieShape.load(legacy)
    raw = json.loads(legacy.read_text())
    first = min(raw["frames"], key=lambda f: f["num"])
    assert shape.title == "Watchmen" and shape.method == "legacy"
    assert len(shape) == len(raw["frames"])
    assert bytes(shape.colors[0]).hex() == first["primalColor"]


@pytest.mark.parametrize(
    "style,size", [("barcode", (300, 100)), ("vertical", (300, 100)), ("ring", (300, 300))]
)
def test_render_sizes(style, size):
    shape = MovieShape("T", np.random.default_rng(0).integers(0, 256, (500, 3)))
    assert render(shape, style=style, width=300, height=100, smooth=5).size == size


def test_barcode_keeps_order():
    shape = MovieShape("T", [[255, 0, 0], [0, 0, 255]])
    img = np.asarray(render(shape, width=10, height=2))
    assert tuple(img[0, 0]) == (255, 0, 0) and tuple(img[0, -1]) == (0, 0, 255)


def test_cli_end_to_end(rgb_video, tmp_path):
    assert main(["analyze", str(rgb_video.parent), "-o", str(tmp_path / "s")]) == 0
    assert main(["render", str(tmp_path / "s"), "-o", str(tmp_path / "i"), "--style", "ring"]) == 0
    assert (tmp_path / "i" / "Red Green Blue.mean.ring.png").exists()
