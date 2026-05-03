"""Photo file management.

Photos are copied into ``data/photos/<uuid>.<ext>`` so the source path can
move or disappear without affecting us. Returned paths are absolute strings,
suitable for storage in ``students.photo_path``.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from app.config import PHOTO_DIR

log = logging.getLogger(__name__)

_ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class PhotoError(Exception):
    """Raised for photo-related problems (missing file, bad extension, etc.)."""


def copy_photo_to_store(source: str | Path) -> str:
    """Copy ``source`` into the photo store under a fresh UUID name.

    Returns the absolute path of the stored file as a string. Raises
    ``PhotoError`` for missing files, oversize files, or unsupported types.
    """
    src = Path(source).expanduser()
    if not src.is_file():
        raise PhotoError(f"Photo not found: {src}")
    ext = src.suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise PhotoError(
            f"Unsupported photo type {ext!r}. Use one of: {', '.join(sorted(_ALLOWED_EXTS))}"
        )
    size = src.stat().st_size
    if size > _MAX_BYTES:
        raise PhotoError(f"Photo too large ({size / 1024 / 1024:.1f} MB > 5 MB limit).")

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    target = PHOTO_DIR / f"{uuid.uuid4().hex}{ext}"
    shutil.copyfile(src, target)
    log.debug("Copied photo %s -> %s", src, target)
    return str(target)


def delete_photo(stored_path: str | None) -> None:
    """Remove a previously stored photo. Silently ignores missing files."""
    if not stored_path:
        return
    p = Path(stored_path)
    try:
        # Only delete if it's actually inside the photo store, never outside.
        p.resolve().relative_to(PHOTO_DIR.resolve())
    except (ValueError, OSError):
        log.warning("Refusing to delete photo outside store: %s", stored_path)
        return
    try:
        p.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Could not delete %s: %s", p, exc)
