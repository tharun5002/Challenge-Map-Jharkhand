"""Registration, JWT login, refresh-token rotation and profile."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status

from api.config import get_settings
from api.deps import CurrentUser
from api.rate_limit import (
    LOGIN_LIMIT,
    REFRESH_LIMIT,
    REGISTER_LIMIT,
    limiter,
)
from api.schemas import (
    LoginRequest,
    LoginResponse,
    PartnerRegisterRequest,
    PartnerRegistrationResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from api.security import (
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    TokenError,
    decode_token,
    hash_password,
    issue_token,
    password_needs_rehash,
    token_digest,
    verify_password,
)
from api.store import connection, create_user, update_user_password
from authentication import validate_new_account

router = APIRouter(prefix="/auth", tags=["auth"])

USER_SELECT = (
    "SELECT id, username, full_name, email, role, district, organization_id, is_active "
    "FROM users"
)

def _user_response(row) -> UserResponse:
    payload = dict(row)
    return UserResponse(
        id=int(payload["id"]),
        username=payload["username"],
        full_name=payload["full_name"] or "",
        email=payload["email"] or None,
        role=payload["role"],
        district=payload["district"],
        organization_id=payload["organization_id"],
    )


def _find_user(
    *, user_id: int | None = None, username: str | None = None
) -> dict | None:
    with connection() as conn:
        if user_id is not None:
            row = conn.execute(USER_SELECT + " WHERE id = ?", (user_id,)).fetchone()
        else:
            row = conn.execute(
                USER_SELECT + " WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
    return None if row is None else dict(row)


def _credentials(email: str) -> dict | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, password_salt, password_hash, is_active "
            "FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
    return None if row is None else dict(row)


def issue_pair(user: dict) -> dict[str, object]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    access = issue_token(
        subject=int(user["id"]),
        role=user["role"],
        token_type=ACCESS_TOKEN,
        secret=settings.jwt_secret,
        ttl=timedelta(minutes=settings.access_ttl_minutes),
    )
    refresh = issue_token(
        subject=int(user["id"]),
        role=user["role"],
        token_type=REFRESH_TOKEN,
        secret=settings.jwt_secret,
        ttl=timedelta(days=settings.refresh_ttl_days),
    )
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_digest, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                int(user["id"]),
                token_digest(refresh),
                (now + timedelta(days=settings.refresh_ttl_days)).isoformat(
                    timespec="seconds"
                ),
                now.isoformat(timespec="seconds"),
            ),
        )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.access_ttl_minutes * 60,
    }


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(REGISTER_LIMIT)
def register(payload: RegisterRequest, request: Request) -> UserResponse:
    try:
        username = validate_new_account(
            payload.username, payload.password, payload.password_confirmation
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    try:
        user_id = create_user(
            username,
            payload.password,
            role="citizen",
            full_name=payload.full_name.strip(),
            email=payload.email,
            district=payload.district,
        )
    except sqlite3.IntegrityError as error:
        message = str(error).lower()
        if "users.username" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already taken.",
            ) from error
        if "users.email" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That email address is already in use.",
            ) from error
        raise

    row = _find_user(user_id=user_id)
    assert row is not None
    return _user_response(row)


@router.post(
    "/register/partner",
    response_model=PartnerRegistrationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(REGISTER_LIMIT)
def register_partner(
    payload: PartnerRegisterRequest, request: Request
) -> PartnerRegistrationResponse:
    try:
        username = validate_new_account(
            payload.username, payload.password, payload.password_confirmation
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    try:
        create_user(
            username,
            payload.password,
            role="partner",
            full_name=payload.full_name.strip(),
            email=payload.email,
            district=payload.district,
            requested_organization_name=payload.organization_name,
            job_title=payload.job_title,
            approval_pending=True,
            is_active=False,
        )
    except sqlite3.IntegrityError as error:
        message = str(error).lower()
        if "users.username" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already taken.",
            ) from error
        if "users.email" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That email address is already in use.",
            ) from error
        raise

    return PartnerRegistrationResponse(
        message="Partner account request submitted for administrator approval."
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(LOGIN_LIMIT)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    credentials = _credentials(payload.email)
    if (
        credentials is None
        or not credentials["is_active"]
        or not verify_password(
            payload.password,
            credentials["password_salt"],
            credentials["password_hash"],
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect for the selected account type.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    row = _find_user(user_id=int(credentials["id"]))
    assert row is not None
    if row["role"] != payload.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect for the selected account type.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if password_needs_rehash(credentials["password_hash"]):
        # Legacy PBKDF2 row (or outdated Argon2id parameters): the plaintext is
        # in hand only here, so this is the one moment the digest can be upgraded.
        update_user_password(
            int(credentials["id"]), *hash_password(payload.password)
        )

    return LoginResponse(**issue_pair(row), user=_user_response(row))


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(REFRESH_LIMIT)
def refresh(payload: RefreshRequest, request: Request) -> TokenPair:
    settings = get_settings()
    try:
        decode_token(
            payload.refresh_token,
            secret=settings.jwt_secret,
            expected_type=REFRESH_TOKEN,
        )
    except TokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error

    digest = token_digest(payload.refresh_token)
    with connection() as conn:
        row = conn.execute(
            "SELECT id, user_id FROM refresh_tokens WHERE token_digest = ?", (digest,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is unknown or was already used.",
            )
        # Rotation: the presented token can never be replayed.
        conn.execute("DELETE FROM refresh_tokens WHERE id = ?", (row["id"],))

    user = _find_user(user_id=int(row["user_id"]))
    if user is None or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is not active.",
        )
    return TokenPair(**issue_pair(user))


@router.get("/me", response_model=UserResponse)
def read_me(current: CurrentUser) -> UserResponse:
    return UserResponse(
        id=current.id,
        username=current.username,
        role=current.role,
        district=current.district,
        organization_id=current.organization_id,
    )
