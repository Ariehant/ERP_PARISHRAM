"""Login / authentication."""

from __future__ import annotations

import logging
import sqlite3

from app.models.user import User
from app.repositories import user_repo
from app.utils.errors import AuthenticationError, ValidationError
from app.utils.security import verify_password

log = logging.getLogger(__name__)


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> User:
    """Verify credentials. Raises ``AuthenticationError`` on failure."""
    if not username or not password:
        raise ValidationError("Username and password are required.")

    user = user_repo.get_by_username(conn, username.strip().lower())
    if user is None:
        log.info("Login failed: unknown user %r", username)
        raise AuthenticationError("Invalid username or password.")
    if not user.is_active:
        log.info("Login blocked: inactive user %r", username)
        raise AuthenticationError("This account has been disabled.")
    if not verify_password(password, user.password_hash):
        log.info("Login failed: bad password for %r", username)
        raise AuthenticationError("Invalid username or password.")

    log.info("Login OK: %s", user.username)
    return user
