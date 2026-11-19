"""Staff issue queue and citizen-visible response updates."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from api.deps import PartnerUser, Principal
from api.routers.complaints import COMPLAINT_SELECT
from api.schemas import ComplaintResponse, StaffResponse, StaffResponseCreate
from api.store import audit, connection, utc_now

router = APIRouter(prefix="/staff", tags=["staff"])


def _district_scope(current: Principal) -> tuple[str, ...] | None:
    """Admins see every report; partner staff see only their org's districts."""
    if current.role == "admin":
        return None
    if current.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This staff account is not linked to an organization.",
        )
    with connection() as conn:
        row = conn.execute(
            "SELECT districts FROM organizations WHERE id = ?",
            (current.organization_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The organization linked to this staff account no longer exists.",
        )
    districts = json.loads(row["districts"])
    if not isinstance(districts, list) or not all(
        isinstance(district, str) for district in districts
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The organization's district coverage is invalid.",
        )
    return tuple(districts)


def _report_for_staff(report_id: str, current: Principal) -> dict:
    districts = _district_scope(current)
    with connection() as conn:
        row = conn.execute(
            COMPLAINT_SELECT + " WHERE report_id = ?", (report_id,)
        ).fetchone()
    if row is None or (
        districts is not None and row["district"] not in districts
    ):
        raise HTTPException(status_code=404, detail="Client issue not found.")
    if row["status"] in {"merged", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Merged or rejected reports cannot receive staff updates.",
        )
    return dict(row)


@router.get("/issues", response_model=list[ComplaintResponse])
def list_client_issues(
    current: PartnerUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ComplaintResponse]:
    districts = _district_scope(current)
    conditions = ["status NOT IN ('merged', 'rejected')"]
    params: list[object] = []
    if districts is not None:
        if not districts:
            return []
        conditions.append(
            "district IN (" + ", ".join("?" for _ in districts) + ")"
        )
        params.extend(districts)
    with connection() as conn:
        rows = conn.execute(
            COMPLAINT_SELECT
            + " WHERE "
            + " AND ".join(conditions)
            + " ORDER BY reported_at DESC, created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [ComplaintResponse(**dict(row)) for row in rows]


@router.post(
    "/issues/{report_id}/responses",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
)
def respond_to_client_issue(
    report_id: str, payload: StaffResponseCreate, current: PartnerUser
) -> StaffResponse:
    _report_for_staff(report_id, current)
    created_at = utc_now()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO staff_responses (report_id, staff_id, status, response_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, current.id, payload.status, payload.response_text, created_at),
        )
        response_id = int(cursor.lastrowid)
        audit(
            conn,
            actor_id=current.id,
            action="staff_response",
            entity_type="complaint",
            entity_id=report_id,
            payload={"status": payload.status},
        )
    return StaffResponse(
        response_id=response_id,
        report_id=report_id,
        status=payload.status,
        response_text=payload.response_text,
        created_at=created_at,
    )
