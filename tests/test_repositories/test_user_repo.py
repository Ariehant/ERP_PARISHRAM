from __future__ import annotations

import sqlite3

import pytest

from app.models.user import User
from app.repositories import user_repo
from app.utils.security import hash_password


def _admin(username: str = "admin") -> User:
    return User(
        id=None,
        username=username,
        password_hash=hash_password("hunter2x"),
        role="admin",
        full_name="Test Admin",
        is_active=True,
    )


def test_create_and_lookup(conn: sqlite3.Connection) -> None:
    assert user_repo.any_user_exists(conn) is False
    uid = user_repo.create_user(conn, _admin())
    assert uid > 0
    assert user_repo.any_user_exists(conn) is True

    fetched = user_repo.get_by_username(conn, "admin")
    assert fetched is not None
    assert fetched.username == "admin"
    assert fetched.role == "admin"
    assert fetched.is_active is True


def test_username_unique(conn: sqlite3.Connection) -> None:
    user_repo.create_user(conn, _admin())
    with pytest.raises(sqlite3.IntegrityError):
        user_repo.create_user(conn, _admin())


def test_get_by_username_missing(conn: sqlite3.Connection) -> None:
    assert user_repo.get_by_username(conn, "nobody") is None
