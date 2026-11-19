"""Administrator console: complaint queue, stats, re-cluster job, staff, matches."""

from __future__ import annotations

import json
import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from api.deps import AdminUser
from api.presenters import match_response
from api.routers.complaints import COMPLAINT_SELECT
from api.routers.partners import MATCH_SELECT
from api.schemas import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    ComplaintResponse,
    MatchDecision,
    MatchResponse,
    ReclusterRequest,
    ReclusterResponse,
    Role,
    StatsResponse,
)
from api.services.clustering import NotEnoughComplaints, recluster
from api.store import audit, connection, create_user, utc_now

router = APIRouter(prefix="/admin", tags=["admin"])

USER_SELECT = (
    "SELECT u.id, u.username, u.full_name, u.email, u.role, u.district, "
    "u.organization_id, COALESCE(o.name, u.requested_organization_name) "
    "AS organization_name, u.job_title, u.approval_pending, u.is_active, "
    "u.created_at FROM users u LEFT JOIN organizations o "
    "ON o.id = u.organization_id"
)


@router.get("/complaints", response_model=list[ComplaintResponse])
def complaint_queue(
    current: AdminUser,
    complaint_status: Annotated[str | None, Query(alias="status")] = None,
    district: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ComplaintResponse]:
    conditions: list[str] = []
    params: list[object] = []
    if complaint_status:
        conditions.append("status = ?")
        params.append(complaint_status)
    if district:
        conditions.append("district = ?")
        params.append(district)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    with connection() as conn:
        rows = conn.execute(
            COMPLAINT_SELECT
            + where
            + " ORDER BY reported_at DESC, created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [ComplaintResponse(**dict(row)) for row in rows]


@router.get("/stats", response_model=StatsResponse)
def stats(current: AdminUser) -> StatsResponse:
    with connection() as conn:
        def count(table: str, where: str = "") -> int:
            return int(
                conn.execute(f"SELECT COUNT(*) AS n FROM {table} {where}").fetchone()["n"]
            )

        return StatsResponse(
            users=count("users"),
            complaints=count("complaints"),
            pending=count("complaints", "WHERE status = 'pending'"),
            clustered=count("complaints", "WHERE status = 'clustered'"),
            merged=count("complaints", "WHERE status = 'merged'"),
            challenges=count("challenges"),
            published=count("challenges", "WHERE status = 'published'"),
            matches=count("matches"),
            feedback=count("feedback"),
        )


@router.post("/jobs/recluster", response_model=ReclusterResponse)
def run_recluster(
    current: AdminUser, payload: ReclusterRequest | None = None
) -> ReclusterResponse:
    try:
        result = recluster(
            clusters=payload.clusters if payload else None, actor_id=current.id
        )
    except NotEnoughComplaints as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return ReclusterResponse(**result)


@router.get("/users", response_model=list[AdminUserResponse])
def list_staff(
    current: AdminUser,
    role: Annotated[Role | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AdminUserResponse]:
    where = " WHERE u.role = ?" if role else ""
    params: tuple[object, ...] = (role,) if role else ()
    with connection() as conn:
        rows = conn.execute(
            USER_SELECT
            + where
            + " ORDER BY u.role, u.username COLLATE NOCASE LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [AdminUserResponse(**dict(row)) for row in rows]


@router.post(
    "/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED
)
def create_staff(payload: AdminUserCreate, current: AdminUser) -> AdminUserResponse:
    payload.validated()
    if payload.organization_id is not None:
        with connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM organizations WHERE id = ?", (payload.organization_id,)
            ).fetchone()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="organization_id does not match a known organization.",
            )
    try:
        user_id = create_user(
            payload.username,
            payload.password,
            role=payload.role,
            full_name=payload.full_name.strip(),
            email=payload.email,
            district=payload.district,
            organization_id=payload.organization_id,
        )
    except sqlite3.IntegrityError as error:
        message = str(error).lower()
        if "users.email" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That email address is already in use.",
            ) from error
        if "users.username" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already taken.",
            ) from error
        raise

    with connection() as conn:
        audit(
            conn,
            actor_id=current.id,
            action="create_user",
            entity_type="user",
            entity_id=user_id,
            payload={"role": payload.role},
        )
        row = conn.execute(USER_SELECT + " WHERE u.id = ?", (user_id,)).fetchone()
    assert row is not None
    return AdminUserResponse(**dict(row))


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_staff(
    user_id: int, payload: AdminUserUpdate, current: AdminUser
) -> AdminUserResponse:
    updates = payload.model_dump(exclude_unset=True)
    if user_id == current.id and (
        "role" in updates or updates.get("is_active") is False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot change your own role or deactivate your own account.",
        )

    with connection() as conn:
        account = conn.execute(
            "SELECT id, role, district, email, requested_organization_name, "
            "approval_pending FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if account is None:
            raise HTTPException(status_code=404, detail="User not found.")

        if updates.get("is_active") is True and account["approval_pending"]:
            if account["role"] == "partner":
                organization_name = account["requested_organization_name"].strip()
                if not organization_name:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This partner application has no organization name.",
                    )
                organization = conn.execute(
                    "SELECT id FROM organizations WHERE name = ? COLLATE NOCASE",
                    (organization_name,),
                ).fetchone()
                if organization is None:
                    cursor = conn.execute(
                        """
                        INSERT INTO organizations (
                            name, org_type, capability_tags, districts, capacity,
                            contact_email, created_at
                        ) VALUES (?, 'Other', '[]', ?, 0.5, ?, ?)
                        """,
                        (
                            organization_name,
                            json.dumps([account["district"]] if account["district"] else []),
                            account["email"] or "",
                            utc_now(),
                        ),
                    )
                    organization_id = int(cursor.lastrowid)
                else:
                    organization_id = int(organization["id"])
                updates["organization_id"] = organization_id
            updates["approval_pending"] = 0

        organization_id = updates.get("organization_id")
        if organization_id is not None:
            known = conn.execute(
                "SELECT 1 FROM organizations WHERE id = ?", (organization_id,)
            ).fetchone()
            if known is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="organization_id does not match a known organization.",
                )

        if updates:
            assignments = ", ".join(f"{column} = ?" for column in updates)
            try:
                conn.execute(
                    f"UPDATE users SET {assignments}, updated_at = ? WHERE id = ?",
                    (*updates.values(), utc_now(), user_id),
                )
            except sqlite3.IntegrityError as error:
                if "users.email" in str(error).lower():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="That email address is already in use.",
                    ) from error
                raise
            audit(
                conn,
                actor_id=current.id,
                action="update_user",
                entity_type="user",
                entity_id=user_id,
                payload=updates,
            )

        row = conn.execute(USER_SELECT + " WHERE u.id = ?", (user_id,)).fetchone()
    assert row is not None
    return AdminUserResponse(**dict(row))


@router.patch("/matches/{match_id}", response_model=MatchResponse)
def decide_match(
    match_id: int, payload: MatchDecision, current: AdminUser
) -> MatchResponse:
    with connection() as conn:
        exists = conn.execute("SELECT 1 FROM matches WHERE id = ?", (match_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Match not found.")
        new_status = "confirmed" if payload.action == "confirm" else "declined"
        conn.execute(
            "UPDATE matches SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, utc_now(), match_id),
        )
        audit(
            conn,
            actor_id=current.id,
            action=payload.action,
            entity_type="match",
            entity_id=match_id,
        )
        updated = conn.execute(
            MATCH_SELECT + " WHERE m.id = ?", (match_id,)
        ).fetchone()
    assert updated is not None
    return match_response(updated)
