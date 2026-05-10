"""Backup + restore using SQLite's online backup API.

- ``auto_backup`` writes ``data/backups/auto_YYYYMMDD_HHMMSS.db`` and
  trims to the most recent ``AUTO_BACKUP_KEEP`` (14) files.
- ``manual_backup`` writes to a user-chosen path.
- ``restore_backup`` renames the current DB to
  ``school.db.replaced.<timestamp>``, copies the chosen file in, and
  asks the caller to restart.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import AUTO_BACKUP_KEEP, BACKUP_DIR, DB_PATH

log = logging.getLogger(__name__)


def _online_backup(src: sqlite3.Connection, target: Path) -> None:
    """Use SQLite's connection.backup API (safe under concurrent writes)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    dst = sqlite3.connect(str(target))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def auto_backup(conn: sqlite3.Connection) -> Path:
    """Write a timestamped backup under ``data/backups/`` and trim old ones."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"auto_{_timestamp()}.db"
    _online_backup(conn, target)
    log.info("Auto-backup written to %s", target)
    _trim_auto_backups(BACKUP_DIR, AUTO_BACKUP_KEEP)
    return target


def manual_backup(conn: sqlite3.Connection, target: str | Path) -> Path:
    """Write a backup to the user-chosen path."""
    target = Path(target)
    _online_backup(conn, target)
    log.info("Manual backup written to %s", target)
    return target


def list_auto_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(
        (p for p in BACKUP_DIR.iterdir() if p.is_file() and p.name.startswith("auto_")),
        key=lambda p: p.name,
        reverse=True,
    )


def _trim_auto_backups(backup_dir: Path, keep: int) -> int:
    files = sorted(
        (p for p in backup_dir.iterdir() if p.is_file() and p.name.startswith("auto_")),
        key=lambda p: p.name,
        reverse=True,
    )
    removed = 0
    for stale in files[keep:]:
        try:
            stale.unlink()
            removed += 1
        except OSError as exc:
            log.warning("Could not delete old backup %s: %s", stale, exc)
    if removed:
        log.info("Trimmed %d old auto-backup(s)", removed)
    return removed


def restore_backup(source: str | Path, db_path: Path | None = None) -> Path:
    """Replace the current DB with ``source``.

    The current DB is renamed to ``<db>.replaced.<timestamp>`` first so
    nothing is destroyed. Caller is responsible for prompting the user
    to restart the app -- the existing connection is invalid afterwards.

    Returns the path of the renamed (old) DB so the caller can mention
    it in the success dialog.
    """
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(f"Backup not found: {src}")
    target = Path(db_path) if db_path is not None else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    replaced_path = target.with_name(f"{target.name}.replaced.{_timestamp()}")
    if target.exists():
        target.rename(replaced_path)
    # Also move the WAL/SHM sidecars if present so SQLite doesn't try to
    # recover from them against the new DB.
    for suffix in ("-wal", "-shm"):
        side = target.with_name(target.name + suffix)
        if side.exists():
            side.unlink()
    shutil.copyfile(src, target)
    log.info("Restored DB from %s; old DB at %s", src, replaced_path)
    return replaced_path
