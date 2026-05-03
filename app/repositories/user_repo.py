"""User repository — login + admin user management."""

from __future__ import annotations

import sqlite3

from app.models.user import User


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        role=row["role"],
        full_name=row["full_name"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )


def any_user_exists(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("SELECT 1 FROM users LIMIT 1")
    return cur.fetchone() is not None


def get_by_username(conn: sqlite3.Connection, username: str) -> User | None:
    cur = conn.execute(
        "SELECT id, username, password_hash, role, full_name, is_active, created_at "
        "FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    return _row_to_user(row) if row else None


def create_user(conn: sqlite3.Connection, user: User) -> int:
    cur = conn.execute(
        """
        INSERT INTO users (username, password_hash, role, full_name, is_active)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user.username,
            user.password_hash,
            user.role,
            user.full_name,
            1 if user.is_active else 0,
        ),
    )
    return int(cur.lastrowid)


def list_users(conn: sqlite3.Connection) -> list[User]:
    cur = conn.execute(
        "SELECT id, username, password_hash, role, full_name, is_active, created_at "
        "FROM users ORDER BY username"
    )
    return [_row_to_user(r) for r in cur.fetchall()]
