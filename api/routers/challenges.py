"""Published challenge browsing, their matches, and admin editing/publishing."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from api.deps import AdminUser, OptionalUser
from api.presenters import challenge_response, match_response
from api.schemas import (
    ChallengeDetailResponse,
    ChallengeDistrict,
    ChallengeEvidence,
    ChallengeResponse,
    ChallengeTrend,
    ChallengeUpdate,
    MatchResponse,
)
from api.store import audit, connection, utc_now

router = APIRouter(prefix="/challenges", tags=["challenges"])

_DISTRICT_JOIN = """
    FROM challenge_complaints cc
    JOIN complaints c ON c.report_id = cc.complaint_report_id
    WHERE cc.challenge_id = challenges.id
"""

CHALLENGE_SELECT = f"""
    SELECT id, slug, title, summary, domain, capability_tags, complaint_count,
           affected_total, severity_score, priority_score, priority_breakdown,
           status, published_at,
           (SELECT COUNT(DISTINCT c.district) {_DISTRICT_JOIN}) AS district_count,
           (SELECT COALESCE(GROUP_CONCAT(DISTINCT c.district), '') {_DISTRICT_JOIN})
               AS district_names,
           (SELECT MIN(c.reported_on) {_DISTRICT_JOIN}) AS first_reported_at,
           (SELECT MAX(c.reported_on) {_DISTRICT_JOIN}) AS last_reported_at
    FROM challenges
"""

MATCH_SELECT = """
    SELECT m.id, m.score, m.breakdown, m.status, c.slug AS challenge_slug,
           c.title AS challenge_title, o.id AS organization_id,
           o.name AS organization_name, o.org_type AS organization_type,
           o.districts AS organization_districts
    FROM matches m
    JOIN challenges c ON c.id = m.challenge_id
    JOIN organizations o ON o.id = m.organization_id
"""


def _fetch(
    *, challenge_id: int | None = None, slug: str | None = None
) -> dict | None:
    with connection() as conn:
        if challenge_id is not None:
            row = conn.execute(
                CHALLENGE_SELECT + " WHERE id = ?", (challenge_id,)
            ).fetchone()
        else:
            row = conn.execute(
                CHALLENGE_SELECT + " WHERE slug = ?", (slug,)
            ).fetchone()
    return None if row is None else dict(row)


def _require_visible(row: dict | None, current) -> dict:
    if row is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    if row["status"] != "published" and (
        current is None or current.role != "admin"
    ):
        raise HTTPException(status_code=404, detail="Challenge not found.")
    return row


@router.get("", response_model=list[ChallengeResponse])
def list_challenges(
    current: OptionalUser,
    challenge_status: Annotated[str | None, Query(alias="status")] = None,
    domain: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ChallengeResponse]:
    conditions: list[str] = []
    params: list[object] = []

    if challenge_status in (None, "", "published"):
        conditions.append("status = 'published'")
    elif current is None or current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list unpublished challenges.",
        )
    elif challenge_status != "all":
        conditions.append("status = ?")
        params.append(challenge_status)

    if domain:
        conditions.append("domain = ?")
        params.append(domain)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    with connection() as conn:
        rows = conn.execute(
            CHALLENGE_SELECT + where + " ORDER BY priority_score DESC, id LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [challenge_response(row) for row in rows]


def _detail(row: dict) -> ChallengeDetailResponse:
    """Attach the report-derived content the public brief renders."""
    base = challenge_response(row)
    with connection() as conn:
        districts = conn.execute(
            """
            SELECT c.district AS district, COUNT(*) AS complaints
            FROM challenge_complaints cc
            JOIN complaints c ON c.report_id = cc.complaint_report_id
            WHERE cc.challenge_id = ?
            GROUP BY c.district
            ORDER BY complaints DESC, c.district
            """,
            (row["id"],),
        ).fetchall()
        evidence = conn.execute(
            """
            SELECT c.raw_text AS quote, c.district AS district,
                   c.reported_on AS reported_at, c.language AS language
            FROM challenge_complaints cc
            JOIN complaints c ON c.report_id = cc.complaint_report_id
            WHERE cc.challenge_id = ? AND c.status <> 'merged'
            ORDER BY c.reported_on DESC
            LIMIT 5
            """,
            (row["id"],),
        ).fetchall()
        timeline = conn.execute(
            """
            SELECT substr(c.reported_on, 1, 7) AS month, COUNT(*) AS complaints
            FROM challenge_complaints cc
            JOIN complaints c ON c.report_id = cc.complaint_report_id
            WHERE cc.challenge_id = ?
            GROUP BY month
            ORDER BY month
            """,
            (row["id"],),
        ).fetchall()
    return ChallengeDetailResponse(
        **base.model_dump(),
        districts=[ChallengeDistrict(**dict(item)) for item in districts],
        evidence=[ChallengeEvidence(**dict(item)) for item in evidence],
        timeline=[ChallengeTrend(**dict(item)) for item in timeline],
    )


@router.get("/{slug}", response_model=ChallengeDetailResponse)
def read_challenge(slug: str, current: OptionalUser) -> ChallengeDetailResponse:
    return _detail(_require_visible(_fetch(slug=slug), current))


@router.get("/{slug}/matches", response_model=list[MatchResponse])
def challenge_matches(slug: str, current: OptionalUser) -> list[MatchResponse]:
    row = _require_visible(_fetch(slug=slug), current)
    with connection() as conn:
        records = conn.execute(
            MATCH_SELECT + " WHERE m.challenge_id = ? ORDER BY m.score DESC",
            (row["id"],),
        ).fetchall()
    return [match_response(record) for record in records]


@router.patch("/{challenge_id}", response_model=ChallengeResponse)
def update_challenge(
    challenge_id: int, payload: ChallengeUpdate, current: AdminUser
) -> ChallengeResponse:
    row = _fetch(challenge_id=challenge_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return challenge_response(row)
    if "domain" in updates:
        updates["capability_tags"] = json.dumps([updates["domain"]])

    assignments = ", ".join(f"{column} = ?" for column in updates)
    with connection() as conn:
        conn.execute(
            f"UPDATE challenges SET {assignments}, updated_at = ? WHERE id = ?",
            (*updates.values(), utc_now(), challenge_id),
        )
        audit(
            conn,
            actor_id=current.id,
            action="update",
            entity_type="challenge",
            entity_id=challenge_id,
            payload=updates,
        )
        updated = conn.execute(
            CHALLENGE_SELECT + " WHERE id = ?", (challenge_id,)
        ).fetchone()
    assert updated is not None
    return challenge_response(updated)


@router.post("/{challenge_id}/publish", response_model=ChallengeResponse)
def publish_challenge(challenge_id: int, current: AdminUser) -> ChallengeResponse:
    row = _fetch(challenge_id=challenge_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    if row["status"] == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An archived challenge cannot be published again.",
        )
    if row["status"] == "published":
        return challenge_response(row)

    now = utc_now()
    with connection() as conn:
        conn.execute(
            """
            UPDATE challenges
            SET status = 'published', published_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, challenge_id),
        )
        audit(
            conn,
            actor_id=current.id,
            action="publish",
            entity_type="challenge",
            entity_id=challenge_id,
        )
        updated = conn.execute(
            CHALLENGE_SELECT + " WHERE id = ?", (challenge_id,)
        ).fetchone()
    assert updated is not None
    return challenge_response(updated)
