"""Centralised paths and constants. No imports from app.* allowed here."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "School ERP"
APP_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------
# Root of the source tree (where this module lives) → its parent is the repo
# root, where data/ sits next to app/.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Allow override via env so PyInstaller / tests can redirect.
DATA_DIR: Path = Path(os.environ.get("SCHOOL_ERP_DATA", PROJECT_ROOT / "data"))

DB_PATH: Path = DATA_DIR / "school.db"
LOG_DIR: Path = DATA_DIR / "logs"
LOG_FILE: Path = LOG_DIR / "app.log"
BACKUP_DIR: Path = DATA_DIR / "backups"
PHOTO_DIR: Path = DATA_DIR / "photos"
DOCUMENT_DIR: Path = DATA_DIR / "documents"

MIGRATIONS_DIR: Path = Path(__file__).resolve().parent / "db" / "migrations"

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 50
AUTO_BACKUP_KEEP = 14

# Dates are ISO strings (YYYY-MM-DD) throughout the codebase.
ISO_DATE_FMT = "%Y-%m-%d"

# Money is stored as integer paise. Helpers in utils/formatters.py.
PAISE_PER_RUPEE = 100


def ensure_runtime_dirs() -> None:
    """Create every runtime directory the app expects. Idempotent."""
    for path in (DATA_DIR, LOG_DIR, BACKUP_DIR, PHOTO_DIR, DOCUMENT_DIR):
        path.mkdir(parents=True, exist_ok=True)
