"""Web interface for Shape Of Movie (FastAPI + Jinja + HTMX)."""

from shapeofmovie.web.app import create_app
from shapeofmovie.web.config import Settings

__all__ = ["Settings", "create_app"]
