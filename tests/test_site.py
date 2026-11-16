"""Static site export: generation, then a real browser on a sub-path, like GitHub Pages."""

import functools
import http.server
import re
import threading
from pathlib import Path

import pytest
from conftest import free_port
from playwright.sync_api import Page, expect

from shapeofmovie.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples" / "mean"


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("pages")
    out = root / "ShapeOfMovie"  # served under /ShapeOfMovie/, as a GitHub project page
    assert main(["site", str(EXAMPLES), "-o", str(out), "--base-path", "ShapeOfMovie"]) == 0
    return out


def test_site_files(site):
    assert (site / "index.html").exists() and (site / ".nojekyll").exists()
    movies = sorted(p.name for p in (site / "movies").iterdir())
    assert movies == ["pulp-fiction", "snowpiercer-le-transperceneige", "spider-man-into-the-spider-verse",
                      "summer-wars", "watchmen"]  # fmt: skip
    for name in ("index.html", "shape.json", "card.png", "barcode.png", "vertical.png", "ring.png"):
        assert (site / "movies" / "watchmen" / name).stat().st_size > 0
    # no absolute links except in 404.html, which uses the base path
    for html in site.rglob("index.html"):
        assert not re.search(r'(href|src)="/(?!/)', html.read_text()), html
    assert 'href="/ShapeOfMovie/assets/app.css"' in (site / "404.html").read_text()


@pytest.fixture(scope="module")
def pages_server(site):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site.parent))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", free_port()), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/ShapeOfMovie/"
    server.shutdown()


@pytest.mark.e2e
def test_static_site_in_browser(pages_server, page: Page):
    errors = []
    page.on("response", lambda r: errors.append(r.url) if r.status >= 400 else None)

    page.goto(pages_server)
    cards = page.get_by_test_id("movie-card")
    expect(cards).to_have_count(5)
    page.wait_for_function("() => [...document.images].every(i => i.complete && i.naturalWidth > 0)")

    cards.filter(has_text="Spider-Man").click()
    expect(page).to_have_url(pages_server + "movies/spider-man-into-the-spider-verse/")
    expect(page.locator(".facts")).to_contain_text("1:56:")

    timeline = page.get_by_test_id("timeline")
    expect(timeline).to_have_attribute("data-ready", "1")
    box = timeline.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(timeline.locator(".tooltip")).to_contain_text(re.compile(r"^58:\d\d · #[0-9a-f]{6}"))

    page.get_by_test_id("style-select").select_option("ring")
    expect(page.get_by_test_id("preview-image")).to_have_attribute("src", "ring.png")
    page.wait_for_function("() => document.querySelector('[data-testid=preview-image]').naturalWidth === 900")

    page.get_by_role("link", name="← Galerie").click()
    expect(cards).to_have_count(5)
    assert errors == []
