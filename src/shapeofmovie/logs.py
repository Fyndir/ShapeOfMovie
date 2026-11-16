"""Logging setup shared by the CLI and the web server.

Configured by environment variables (or CLI flags, which take precedence):
    SOM_LOG_LEVEL  DEBUG, INFO (default), WARNING, ERROR
    SOM_LOG_FILE   also write to this file, rotated at 10 MB (5 files kept)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None, file: str | Path | None = None) -> None:
    """Configure the root logger. Safe to call several times (handlers are replaced)."""
    level_name = (level or os.environ.get("SOM_LOG_LEVEL") or "INFO").upper()
    numeric = logging.getLevelName(level_name)
    if not isinstance(numeric, int):
        raise ValueError(f"unknown log level '{level_name}'")
    file = file or os.environ.get("SOM_LOG_FILE") or None

    formatter = logging.Formatter(FORMAT, DATE_FORMAT)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if file:
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(file, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
        )

    root = logging.getLogger()
    for old in root.handlers[:]:
        root.removeHandler(old)
        old.close()
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(numeric)

    # uvicorn installs its own handlers: route everything through ours instead
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("PIL").setLevel(max(numeric, logging.INFO))  # very chatty at DEBUG
