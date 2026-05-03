from __future__ import annotations

import pytest

from app.utils.security import hash_password, verify_password


def test_hash_verify_round_trip() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("hunter2x")
    assert verify_password("hunter2", h) is False
    assert verify_password("Hunter2x", h) is False


def test_hash_is_unique_per_call() -> None:
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b


def test_verify_garbage_returns_false() -> None:
    assert verify_password("anything", "") is False
    assert verify_password("anything", "not-a-hash") is False
    assert verify_password("anything", "scrypt$junk") is False


def test_hash_rejects_empty() -> None:
    with pytest.raises(ValueError):
        hash_password("")
