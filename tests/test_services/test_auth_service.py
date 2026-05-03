from __future__ import annotations

import sqlite3

import pytest

from app.models.user import User
from app.repositories import user_repo
from app.services.auth_service import authenticate
from app.utils.errors import AuthenticationError, ValidationError
from app.utils.security import hash_password


def _seed(conn: sqlite3.Connection, *, active: bool = True) -> None:
    user_repo.create_user(
        conn,
        User(
            id=None,
            username="admin",
            password_hash=hash_password("hunter2x"),
            role="admin",
            full_name="Principal",
            is_active=active,
        ),
    )


def test_authenticate_success(conn: sqlite3.Connection) -> None:
    _seed(conn)
    user = authenticate(conn, "admin", "hunter2x")
    assert user.username == "admin"


def test_authenticate_uppercase_username(conn: sqlite3.Connection) -> None:
    _seed(conn)
    user = authenticate(conn, "ADMIN", "hunter2x")
    assert user.username == "admin"


def test_authenticate_bad_password(conn: sqlite3.Connection) -> None:
    _seed(conn)
    with pytest.raises(AuthenticationError):
        authenticate(conn, "admin", "wrong")


def test_authenticate_unknown_user(conn: sqlite3.Connection) -> None:
    _seed(conn)
    with pytest.raises(AuthenticationError):
        authenticate(conn, "ghost", "any")


def test_authenticate_inactive_user(conn: sqlite3.Connection) -> None:
    _seed(conn, active=False)
    with pytest.raises(AuthenticationError):
        authenticate(conn, "admin", "hunter2x")


def test_authenticate_validation(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValidationError):
        authenticate(conn, "", "")
