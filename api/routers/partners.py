"""Partner directory, a partner's matched challenges, and interest expressions."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from api.deps import PartnerUser
from api.presenters import match_response
from api.schemas import MatchResponse, PartnerResponse
from api.store import audit, connection, utc_now

router = APIRouter(tags=["partners"])

MATCH_SELECT = """
    SELECT m.id, m.score, m.breakdown, m.status, c.slug AS challenge_slug,
           c.title AS challenge_title, o.id AS organization_id,
           o.name AS organization_name, o.org_type AS organization_type,
           o.districts AS organization_districts
    FROM matches m
    JOIN challenges c ON c.id = m.challenge_id
    JOIN organizations o ON o.id = m.organization_id
"""


def _partner(row) -> PartnerResponse:
    payload = dict(row)
    return PartnerResponse(
        id=int(payload["id"]),
        name=payload["name"],
        org_type=payload["org_type"],
        capability_tags=json.loads(payload["capability_tags"]),
        districts=json.loads(payload["districts"]),
        capacity=float(payload["capacity"]),
        contact_email=payload["contact_email"],
    )


@router.get("/partners", response_model=list[PartnerResponse])
def list_partners() -> list[PartnerResponse]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM organizations ORDER BY name").fetchall()
    return [_partner(row) for row in rows]


@router.get("/partners/me/matches", response_model=list[MatchResponse])
def my_matches(current: PartnerUser) -> list[MatchResponse]:
    if current.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This partner account is not linked to an organization.",
        )
    with connection() as conn:
        rows = conn.execute(
            MATCH_SELECT
            + " WHERE m.organization_id = ? AND c.status = 'published' "
            "ORDER BY m.score DESC",
            (current.organization_id,),
        ).fetchall()
    return [match_response(row) for row in rows]


@router.post("/matches/{match_id}/interest", response_model=MatchResponse)
def express_interest(match_id: int, current: PartnerUser) -> MatchResponse:
    if current.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This partner account is not linked to an organization.",
        )
    with connection() as conn:
        row = conn.execute(
            """
            SELECT m.id, m.organization_id, m.status, c.status AS challenge_status
            FROM matches m
            JOIN challenges c ON c.id = m.challenge_id
            WHERE m.id = ?
            """,
            (match_id,),
        ).fetchone()
        if row is None or row["organization_id"] != current.organization_id:
            raise HTTPException(status_code=404, detail="Match not found.")
        if row["challenge_status"] != "published":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interest can only be expressed for a published challenge.",
            )
        if row["status"] == "declined":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This match was declined.",
            )
        conn.execute(
            "UPDATE matches SET status = 'expressed_interest', updated_at = ? WHERE id = ?",
            (utc_now(), match_id),
        )
        audit(
            conn,
            actor_id=current.id,
            action="express_interest",
            entity_type="match",
            entity_id=match_id,
        )
        updated = conn.execute(
            MATCH_SELECT + " WHERE m.id = ?", (match_id,)
        ).fetchone()
    assert updated is not None
    return match_response(updated)
