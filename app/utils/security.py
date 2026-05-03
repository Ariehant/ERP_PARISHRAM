"""Password hashing using stdlib ``hashlib.scrypt``.

Storage format::

    scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>

Tuned for an i3 with 4 GB RAM: n=2**14, r=8, p=1 (~32 MB working memory).
Verifies in well under 100 ms on typical hardware.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_SCRYPT_N = 2**14  # 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def _b64encode(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64decode(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def hash_password(password: str) -> str:
    """Return a self-describing hash string for ``password``."""
    if not isinstance(password, str) or password == "":
        raise ValueError("password must be a non-empty string")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64encode(salt)}${_b64encode(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify ``password`` against a previously stored hash."""
    if not stored or not stored.startswith("scrypt$"):
        return False
    try:
        algo, n_s, r_s, p_s, salt_b64, hash_b64 = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    try:
        n, r, p = int(n_s), int(r_s), int(p_s)
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=len(expected),
        maxmem=64 * 1024 * 1024,
    )
    return hmac.compare_digest(candidate, expected)
