"""Shape of Movie: summarise a whole movie as a single image of its colours."""

from shapeofmovie.analyze import analyze
from shapeofmovie.models import MovieShape
from shapeofmovie.render import render

__all__ = ["MovieShape", "analyze", "render"]
__version__ = "2.0.0.dev0"
