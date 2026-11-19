"""Row-to-response conversions shared by several routers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from api.schemas import ChallengeResponse, MatchResponse


def _severity_label(score: float) -> str:
    """Map the stored 0..1 severity component onto the four UI labels."""
    if score >= 0.85:
        return "critical"
    if score >= 0.7:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def challenge_response(row: sqlite3.Row | dict[str, Any]) -> ChallengeResponse:
    payload = dict(row)
    names = str(payload.get("district_names") or "")
    return ChallengeResponse(
        id=int(payload["id"]),
        slug=payload["slug"],
        title=payload["title"],
        summary=payload["summary"],
        domain=payload["domain"],
        complaint_count=int(payload["complaint_count"]),
        affected_total=int(payload["affected_total"]),
        severity_score=float(payload["severity_score"]),
        severity=_severity_label(float(payload["severity_score"])),
        tags=json.loads(payload.get("capability_tags") or "[]"),
        priority_score=float(payload["priority_score"]),
        priority_breakdown=json.loads(payload["priority_breakdown"] or "{}"),
        status=payload["status"],
        published_at=payload["published_at"],
        district_count=int(payload.get("district_count") or 0),
        district_names=[name for name in names.split(",") if name],
        first_reported_at=payload.get("first_reported_at"),
        last_reported_at=payload.get("last_reported_at"),
    )


def match_response(row: sqlite3.Row | dict[str, Any]) -> MatchResponse:
    payload = dict(row)
    return MatchResponse(
        id=int(payload["id"]),
        challenge_slug=payload["challenge_slug"],
        challenge_title=payload["challenge_title"],
        organization_id=int(payload["organization_id"]),
        organization_name=payload["organization_name"],
        organization_type=payload.get("organization_type") or "",
        organization_districts=json.loads(
            payload.get("organization_districts") or "[]"
        ),
        score=float(payload["score"]),
        breakdown=json.loads(payload["breakdown"] or "{}"),
        status=payload["status"],
    )
