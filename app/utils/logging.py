"""Logging setup. Rotating file handler at ``data/logs/app.log``.

Default level INFO; pass ``debug=True`` (e.g. from ``--debug``) for DEBUG.
A console handler is added too so developers see output during ``python -m``
runs; PyInstaller'd executables still get the file handler.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import LOG_DIR, LOG_FILE

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3


def configure_logging(debug: bool = False) -> None:
    """Configure root logging exactly once. Safe to call multiple times."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Replace any pre-existing handlers we own (idempotent).
    for handler in list(root.handlers):
        if getattr(handler, "_school_erp", False):
            root.removeHandler(handler)

    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler._school_erp = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(level)
    console._school_erp = True  # type: ignore[attr-defined]
    root.addHandler(console)
