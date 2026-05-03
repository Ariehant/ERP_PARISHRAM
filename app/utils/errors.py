"""Domain-level exceptions.

Repositories raise sqlite3 errors (or wrap them as ``RepositoryError``).
Services raise ``ValidationError`` for user-facing input problems and
``AuthenticationError`` for auth failures. UI layers translate these into
dialogs.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application-level exceptions."""


class ValidationError(AppError):
    """Raised by services when user-supplied data fails validation.

    The ``field`` attribute (optional) lets the UI highlight the offending
    form field. ``message`` is always safe to display to the user.
    """

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class AuthenticationError(AppError):
    """Raised when login fails (bad credentials, inactive user, etc.)."""


class RepositoryError(AppError):
    """Raised by repositories when a SQL constraint or integrity rule fails."""


class MigrationError(AppError):
    """Raised when a database migration cannot be applied."""
