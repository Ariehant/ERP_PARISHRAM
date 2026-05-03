from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _setup_photo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SCHOOL_ERP_DATA", str(tmp_path))
    import app.config
    import app.utils.photos

    importlib.reload(app.config)
    importlib.reload(app.utils.photos)
    return app.config.PHOTO_DIR


def test_copy_photo_to_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    photo_dir = _setup_photo_dir(tmp_path, monkeypatch)
    from app.utils.photos import copy_photo_to_store

    src = tmp_path / "child.jpg"
    src.write_bytes(b"\xff\xd8\xff" + b"0" * 1000)  # JPEG magic + bytes

    stored = copy_photo_to_store(src)
    stored_path = Path(stored)
    assert stored_path.is_file()
    assert stored_path.parent == photo_dir
    assert stored_path.suffix == ".jpg"
    # Content preserved.
    assert stored_path.read_bytes() == src.read_bytes()


def test_rejects_unsupported_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_photo_dir(tmp_path, monkeypatch)
    from app.utils.photos import PhotoError, copy_photo_to_store

    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF")
    with pytest.raises(PhotoError):
        copy_photo_to_store(src)


def test_rejects_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_photo_dir(tmp_path, monkeypatch)
    from app.utils.photos import PhotoError, copy_photo_to_store

    with pytest.raises(PhotoError):
        copy_photo_to_store(tmp_path / "nope.jpg")


def test_delete_photo_only_removes_inside_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    photo_dir = _setup_photo_dir(tmp_path, monkeypatch)
    from app.utils.photos import copy_photo_to_store, delete_photo

    src = tmp_path / "x.png"
    src.write_bytes(b"\x89PNG" + b"0" * 100)
    stored = copy_photo_to_store(src)
    assert Path(stored).is_file()

    # delete_photo on stored should succeed.
    delete_photo(stored)
    assert not Path(stored).exists()

    # delete_photo on a path outside the store is silently refused.
    outside = tmp_path / "outside.txt"
    outside.write_text("keep me")
    delete_photo(str(outside))
    assert outside.exists()

    # Sanity: photo dir still exists.
    assert photo_dir.is_dir()
