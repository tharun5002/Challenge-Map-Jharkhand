"""Password hashing and JWT issuing/verification.

Passwords are hashed with Argon2id in ``authentication.py``. Legacy
PBKDF2-SHA256 rows still verify and are rehashed on the next successful login,
so the upgrade never locks an existing account out.

Refresh tokens are opaque JWTs stored *hashed* in the database, so a leaked
database copy cannot be replayed against the API.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from authentication import hash_password, password_needs_rehash, verify_password

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"
ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when a token is missing a claim, expired, or of the wrong type."""


def issue_token(
    *,
    subject: int,
    role: str,
    token_type: str,
    secret: str,
    ttl: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "type": token_type,
        # Two logins in the same second would otherwise produce the same token
        # claims, and therefore the same digest, colliding on the unique index.
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, *, secret: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as error:
        raise TokenError("invalid or expired token") from error
    if payload.get("type") != expected_type:
        raise TokenError(f"expected a {expected_type} token")
    return payload


def token_digest(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
    "TokenError",
    "decode_token",
    "hash_password",
    "issue_token",
    "password_needs_rehash",
    "token_digest",
    "verify_password",
]
