"""Authentication and role dependencies.

Access tokens are validated as JWTs; the database is re-read on every request so
a disabled account loses access immediately instead of when its token expires.
HTTP Basic is still accepted as a fallback so the existing citizen endpoints and
their tests keep working while the frontend moves to Bearer tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)

from api.config import get_settings
from api.security import ACCESS_TOKEN, TokenError, decode_token, verify_password
from api.store import connection

bearer_scheme = HTTPBearer(auto_error=False)
basic_scheme = HTTPBasic(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: int
    username: str
    role: str
    district: str | None
    organization_id: int | None


def _unauthorized(detail: str, scheme: str = "Bearer") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": scheme},
    )


def _load_principal(user_id: int) -> Principal:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, username, role, district, organization_id, is_active "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None or not row["is_active"]:
        raise _unauthorized("This account is not active.")
    return Principal(
        id=int(row["id"]),
        username=row["username"],
        role=row["role"],
        district=row["district"],
        organization_id=row["organization_id"],
    )


def _from_basic(credentials: HTTPBasicCredentials) -> Principal:
    email = credentials.username.strip()
    with connection() as conn:
        row = conn.execute(
            "SELECT id, password_salt, password_hash, is_active "
            "FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
    if row is None or not row["is_active"]:
        raise _unauthorized("Valid credentials are required.", scheme="Basic")
    if not verify_password(
        credentials.password, row["password_salt"], row["password_hash"]
    ):
        raise _unauthorized("Valid credentials are required.", scheme="Basic")
    return _load_principal(int(row["id"]))


def get_current_user(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    basic: Annotated[HTTPBasicCredentials | None, Depends(basic_scheme)],
) -> Principal:
    if bearer is not None:
        try:
            payload = decode_token(
                bearer.credentials,
                secret=get_settings().jwt_secret,
                expected_type=ACCESS_TOKEN,
            )
        except TokenError as error:
            raise _unauthorized(str(error)) from error
        try:
            user_id = int(payload.get("sub", ""))
        except (TypeError, ValueError) as error:
            raise _unauthorized("Invalid token subject.") from error
        return _load_principal(user_id)
    if basic is not None:
        return _from_basic(basic)
    raise _unauthorized("Authentication is required.")


def get_optional_user(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    basic: Annotated[HTTPBasicCredentials | None, Depends(basic_scheme)],
) -> Principal | None:
    if bearer is None and basic is None:
        return None
    return get_current_user(bearer, basic)


def require_role(*roles: str):
    """Build a dependency that requires one of ``roles`` (403 when authenticated)."""

    def dependency(
        current: Annotated[Principal, Depends(get_current_user)],
    ) -> Principal:
        if current.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires role: " + ", ".join(roles) + ".",
            )
        return current

    return dependency


CurrentUser = Annotated[Principal, Depends(get_current_user)]
OptionalUser = Annotated[Principal | None, Depends(get_optional_user)]
CitizenUser = Annotated[Principal, Depends(require_role("citizen"))]
AdminUser = Annotated[Principal, Depends(require_role("admin"))]
PartnerUser = Annotated[Principal, Depends(require_role("partner", "admin"))]
