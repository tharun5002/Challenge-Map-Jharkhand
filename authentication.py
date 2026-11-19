"""Password and citizen-account validation helpers.

Passwords are hashed with **Argon2id** (RFC 9106) through ``argon2-cffi``. The
PHC string (``$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>``) is stored in the
``password_hash`` column and the ``password_salt`` column carries the scheme
marker ``argon2id``, so every row states the algorithm that produced it.

Rows created before the upgrade hold a hex PBKDF2-SHA256 digest. Those still
verify — dropping them would lock every existing account out — and the API
rehashes them to Argon2id on the next successful login via
:func:`password_needs_rehash`. No account is stranded on the old scheme, and
nothing claims Argon2id while holding PBKDF2.

``argon2-cffi`` is imported lazily so that username/password *validation* can be
used without the hashing dependency installed; the error when it is missing
names the requirement file instead of an opaque ImportError.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Any

LEGACY_PASSWORD_ITERATIONS = 600_000
# Kept for callers that still refer to the old constant name.
PASSWORD_ITERATIONS = LEGACY_PASSWORD_ITERATIONS

ARGON2_MARKER = "argon2id"
ARGON2_PREFIX = "$argon2id$"

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,31}\Z")

_hasher: Any | None = None


def _argon2_hasher() -> Any:
    """Return the process-wide Argon2id hasher, importing argon2 lazily."""
    global _hasher
    if _hasher is None:
        try:
            from argon2 import PasswordHasher
        except ImportError as error:  # pragma: no cover - dependency is declared
            raise RuntimeError(
                "Password hashing needs argon2-cffi. Install it with "
                "'python -m pip install -r requirements/api.txt'."
            ) from error
        # argon2-cffi defaults: Argon2id, t=3, m=64 MiB, p=4, 16-byte salt,
        # 32-byte digest. Written into the PHC string, so verification never
        # depends on these constants staying put.
        _hasher = PasswordHasher()
    return _hasher


def hash_password(password: str) -> tuple[str, str]:
    """Return ``(scheme marker, Argon2id PHC hash)`` for storage.

    The two-element shape matches the existing ``password_salt`` /
    ``password_hash`` columns, so the schema does not change.
    """
    return ARGON2_MARKER, _argon2_hasher().hash(password)


def verify_password(password: str, salt_hex: str, password_hash_hex: str) -> bool:
    """Check a password against either an Argon2id or a legacy PBKDF2 row."""
    stored = password_hash_hex or ""
    if stored.startswith(ARGON2_PREFIX):
        from argon2.exceptions import (
            InvalidHashError,
            VerificationError,
            VerifyMismatchError,
        )

        try:
            return bool(_argon2_hasher().verify(stored, password))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    # Legacy PBKDF2-SHA256 row written before the Argon2id upgrade.
    try:
        salt = bytes.fromhex(salt_hex or "")
        expected_hash = bytes.fromhex(stored)
    except ValueError:
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, LEGACY_PASSWORD_ITERATIONS
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def password_needs_rehash(password_hash_hex: str) -> bool:
    """True when a stored digest is legacy, or weaker than today's parameters."""
    stored = password_hash_hex or ""
    if not stored.startswith(ARGON2_PREFIX):
        return True
    try:
        return bool(_argon2_hasher().check_needs_rehash(stored))
    except Exception:  # noqa: BLE001 - an unreadable hash must be replaced
        return True


def validate_new_account(
    username: str, password: str, password_confirmation: str
) -> str:
    normalized_username = username.strip()
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise ValueError(
            "Username must be 3–32 characters, start with a letter or number, "
            "and use only letters, numbers, dots, underscores, or hyphens."
        )
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    if len(password) > 128:
        raise ValueError("Password must be no more than 128 characters.")
    if password != password_confirmation:
        raise ValueError("The password confirmation does not match.")
    return normalized_username
