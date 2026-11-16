"""Static site export: a read-only showcase that any static host can serve (GitHub Pages…).

Everything is pre-rendered (pages, images, data) and every link is relative, so the
site works from a sub-path such as https://user.github.io/ShapeOfMovie/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from shapeofmovie import __version__
from shapeofmovie.models import MovieShape
from shapeofmovie.render import render

HERE = Path(__file__).parent

# (style, width, height) of the pre-rendered images
CARD = ("barcode", 640, 160)
RENDERS = {"barcode": (1600, 400), "vertical": (480, 800), "ring": (900, 900)}
STYLE_LABELS = {"barcode": "Code-barres", "vertical": "Vertical", "ring": "Anneau"}


def build_site(
    shape_files: list[Path],
    output: Path,
    *,
    title: str = "Shape Of Movie",
    smooth: int = 5,
    base_path: str = "/",
) -> list[str]:
    """Write the site to `output` (replaced if it exists). Returns the movie ids.

    base_path is only used by 404.html, which can be served at any depth: "/ShapeOfMovie/"
    for a GitHub project page, "/" for a domain of its own.
    """
    base_path = "/" + base_path.strip("/") + "/" if base_path.strip("/") else "/"
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    from shapeofmovie.web.app import METHOD_LABELS, fmt_duration, movie_summary, palette
    from shapeofmovie.web.store import slugify

    if output.exists():
        shutil.rmtree(output)
    (output / "assets").mkdir(parents=True)
    for asset in ("app.css", "app.js"):
        shutil.copy(HERE / "web" / "static" / asset, output / "assets" / asset)

    movies: list[tuple[dict, MovieShape]] = []
    used: set[str] = set()
    for file in shape_files:
        shape = MovieShape.load(file)
        movie_id = slugify(shape.title)
        while movie_id in used:
            movie_id += "-2"
        used.add(movie_id)
        movies.append((movie_summary(movie_id, shape), shape))
    movies.sort(key=lambda m: m[0]["title"].lower())

    env = Environment(
        loader=FileSystemLoader(HERE / "site_templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["duration"] = fmt_duration
    env.globals.update(site_title=title, version=__version__, methods=METHOD_LABELS, styles=STYLE_LABELS)

    for movie, shape in movies:
        mid = movie["id"]
        folder = output / "movies" / mid
        folder.mkdir(parents=True)
        style, w, h = CARD
        render(shape, style, width=w, height=h, smooth=smooth).save(folder / "card.png", optimize=True)
        for style, (w, h) in RENDERS.items():
            render(shape, style, width=w, height=h, smooth=smooth).save(
                folder / f"{style}.png", optimize=True
            )
        shape.save(folder / "shape.json")
        html = env.get_template("movie.html").render(root="../../", movie=movie, palette=palette(shape))
        (folder / "index.html").write_text(html, encoding="utf-8")

    index = env.get_template("index.html").render(root="", movies=[m for m, _ in movies])
    (output / "index.html").write_text(index, encoding="utf-8")
    (output / "404.html").write_text(env.get_template("404.html").render(root=base_path), encoding="utf-8")
    (output / ".nojekyll").touch()  # serve files as-is, no Jekyll processing
    return [m["id"] for m, _ in movies]
