"""Analysed movies, stored as one JSON file per movie."""

from __future__ import annotations

import logging
import re
import secrets
import threading
import unicodedata
from pathlib import Path

from shapeofmovie.models import MovieShape

log = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-z0-9-]{1,80}$")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "movie"


class ShapeStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, MovieShape]] = {}

    def _path(self, movie_id: str) -> Path:
        if not _ID_RE.match(movie_id):  # also blocks path traversal
            raise KeyError(movie_id)
        return self.directory / f"{movie_id}.json"

    def new_id(self, title: str) -> str:
        return f"{slugify(title)}-{secrets.token_hex(3)}"

    def save(self, movie_id: str, shape: MovieShape) -> None:
        path = self._path(movie_id)
        tmp = path.with_suffix(".json.part")
        shape.save(tmp)
        tmp.replace(path)
        log.info("saved movie %s (%d samples)", movie_id, len(shape))

    def get(self, movie_id: str) -> MovieShape:
        path = self._path(movie_id)
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            raise KeyError(movie_id) from None
        with self._lock:
            cached = self._cache.get(movie_id)
            if cached and cached[0] == mtime:
                return cached[1]
        shape = MovieShape.load(path)
        with self._lock:
            self._cache[movie_id] = (mtime, shape)
        return shape

    def list(self) -> list[tuple[str, MovieShape]]:
        """All movies, most recently added first."""
        files = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [(p.stem, self.get(p.stem)) for p in files]

    def delete(self, movie_id: str) -> None:
        self._path(movie_id).unlink(missing_ok=False)
        log.info("deleted movie %s", movie_id)
        with self._lock:
            self._cache.pop(movie_id, None)

    def __contains__(self, movie_id: str) -> bool:
        try:
            return self._path(movie_id).exists()
        except KeyError:
            return False
