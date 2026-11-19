"""Complaint submission, owner-scoped access, merge and resolution feedback."""

from __future__ import annotations

import logging
import threading
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status

from api.config import get_settings
from api.deps import CitizenUser, CurrentUser, Principal
from api.rate_limit import SUBMIT_LIMIT, limiter
from api.services.clustering import NotEnoughComplaints, recluster
from api.schemas import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintSubmitResponse,
    FeedbackCreate,
    FeedbackResponse,
    MergeRequest,
)
from api.services.dedup import duplicate_candidates
from api.store import audit, connection, new_report_id, utc_now

router = APIRouter(prefix="/complaints", tags=["complaints"])

logger = logging.getLogger(__name__)

# Submissions queue a background re-cluster. One run at a time is enough, but a
# report that arrives mid-run must not be missed: the event makes the running
# job loop once more instead of leaving the new report pending.
_cluster_lock = threading.Lock()
_cluster_queued = threading.Event()


def auto_cluster() -> None:
    """Refresh draft challenges after a submission, off the request path."""
    _cluster_queued.set()
    if not _cluster_lock.acquire(blocking=False):
        return
    try:
        while _cluster_queued.is_set():
            _cluster_queued.clear()
            try:
                recluster(actor_id=None)
            except NotEnoughComplaints:
                # A single report is not a cluster yet; the next submission retries.
                continue
            except Exception:  # noqa: BLE001 - a background failure must be logged
                logger.exception("Automatic clustering failed")
                break
    finally:
        _cluster_lock.release()

COMPLAINT_SELECT = """
    SELECT report_id, district, place, raw_text AS report_text, language, severity,
           affected_population, status, duplicate_of, reported_on AS reported_at,
           created_at, source, is_synthetic,
           (SELECT status FROM staff_responses
            WHERE staff_responses.report_id = complaints.report_id
            ORDER BY created_at DESC, id DESC LIMIT 1) AS staff_response_status,
           (SELECT response_text FROM staff_responses
            WHERE staff_responses.report_id = complaints.report_id
            ORDER BY created_at DESC, id DESC LIMIT 1) AS staff_response_text,
           (SELECT created_at FROM staff_responses
            WHERE staff_responses.report_id = complaints.report_id
            ORDER BY created_at DESC, id DESC LIMIT 1) AS staff_responded_at
    FROM complaints
"""


def _owner_id(report_id: str) -> int | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT owner_id FROM complaints WHERE report_id = ?", (report_id,)
        ).fetchone()
    return None if row is None else row["owner_id"]


def _fetch(report_id: str) -> dict | None:
    with connection() as conn:
        row = conn.execute(
            COMPLAINT_SELECT + " WHERE report_id = ?", (report_id,)
        ).fetchone()
    return None if row is None else dict(row)


def require_access(report_id: str, principal: Principal) -> dict:
    """Return the complaint, or 404 when it does not exist or is not theirs.

    A citizen must not be able to probe for another citizen's report ids, so an
    unauthorised read is reported as missing rather than forbidden.
    """
    owner = _owner_id(report_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    if principal.role != "admin" and owner != principal.id:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    row = _fetch(report_id)
    assert row is not None
    return row


@router.post(
    "",
    response_model=ComplaintSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(SUBMIT_LIMIT)
def create_complaint(
    payload: ComplaintCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current: CitizenUser,
) -> ComplaintSubmitResponse:
    report_id = new_report_id()
    now = utc_now()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO complaints (
                report_id, owner_id, district, place, raw_text, language, severity,
                affected_population, status, reported_on, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                report_id,
                current.id,
                payload.district,
                payload.place,
                payload.report_text,
                payload.language,
                payload.severity,
                payload.affected_population,
                now,
                now,
                now,
            ),
        )
        audit(
            conn,
            actor_id=current.id,
            action="submit",
            entity_type="complaint",
            entity_id=report_id,
        )
        row = conn.execute(
            COMPLAINT_SELECT + " WHERE report_id = ?", (report_id,)
        ).fetchone()

    candidates = duplicate_candidates(
        report_id,
        payload.district,
        payload.report_text,
        threshold=get_settings().dedup_threshold,
    )
    # Cluster after the response is sent, so the submitter is never waiting on
    # the NLP job and the queue is grouped without an administrator clicking.
    background_tasks.add_task(auto_cluster)
    assert row is not None
    return ComplaintSubmitResponse(**dict(row), duplicate_candidates=candidates)


@router.get("", response_model=list[ComplaintResponse])
def list_complaints(
    current: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ComplaintResponse]:
    with connection() as conn:
        if current.role == "admin":
            rows = conn.execute(
                COMPLAINT_SELECT
                + " ORDER BY reported_at DESC, created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                COMPLAINT_SELECT
                + " WHERE owner_id = ? ORDER BY reported_at DESC, created_at DESC "
                "LIMIT ? OFFSET ?",
                (current.id, limit, offset),
            ).fetchall()
    return [ComplaintResponse(**dict(row)) for row in rows]


@router.get("/{report_id}", response_model=ComplaintResponse)
def read_complaint(report_id: str, current: CurrentUser) -> ComplaintResponse:
    return ComplaintResponse(**require_access(report_id, current))


@router.post("/{report_id}/merge", response_model=ComplaintResponse)
def merge_complaint(
    report_id: str, payload: MergeRequest, current: CurrentUser
) -> ComplaintResponse:
    """Attach the caller's report to an existing report in the same district."""
    source = require_access(report_id, current)
    if payload.keep_report_id == report_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A complaint cannot be merged into itself.",
        )
    if source["status"] == "merged" or source["duplicate_of"] is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This complaint is already merged into another report.",
        )

    # Ownership of the target is deliberately not required: attaching only
    # changes this citizen's report, never the one being attached to. The
    # target must exist in the same district (the block the duplicate check
    # uses) and must not itself be merged, so chains cannot form.
    with connection() as conn:
        target = conn.execute(
            "SELECT report_id, district, status, duplicate_of "
            "FROM complaints WHERE report_id = ?",
            (payload.keep_report_id,),
        ).fetchone()
        if target is None or target["district"] != source["district"]:
            raise HTTPException(status_code=404, detail="Complaint not found.")
        if target["status"] == "merged" or target["duplicate_of"] is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That report is already merged into another report.",
            )
        conn.execute(
            """
            UPDATE complaints
            SET duplicate_of = ?, status = 'merged', updated_at = ?
            WHERE report_id = ?
            """,
            (payload.keep_report_id, utc_now(), report_id),
        )
        audit(
            conn,
            actor_id=current.id,
            action="merge",
            entity_type="complaint",
            entity_id=report_id,
            payload={"kept": payload.keep_report_id},
        )
        row = conn.execute(
            COMPLAINT_SELECT + " WHERE report_id = ?", (report_id,)
        ).fetchone()
    assert row is not None
    return ComplaintResponse(**dict(row))


@router.post(
    "/{report_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_feedback(
    report_id: str, payload: FeedbackCreate, current: CurrentUser
) -> FeedbackResponse:
    require_access(report_id, current)
    submitted_at = utc_now()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO feedback (report_id, status, feedback_text, submitted_by, submitted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, payload.status, payload.feedback_text, current.id, submitted_at),
        )
        feedback_id = int(cursor.lastrowid)
    return FeedbackResponse(
        feedback_id=feedback_id,
        report_id=report_id,
        status=payload.status,
        feedback_text=payload.feedback_text,
        submitted_at=submitted_at,
    )


@router.get("/{report_id}/feedback", response_model=list[FeedbackResponse])
def list_feedback(report_id: str, current: CurrentUser) -> list[FeedbackResponse]:
    require_access(report_id, current)
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, report_id, status, feedback_text, submitted_at
            FROM feedback
            WHERE report_id = ?
            ORDER BY submitted_at DESC, id DESC
            """,
            (report_id,),
        ).fetchall()
    return [
        FeedbackResponse(
            feedback_id=int(row["id"]),
            report_id=row["report_id"],
            status=row["status"],
            feedback_text=row["feedback_text"],
            submitted_at=row["submitted_at"],
        )
        for row in rows
    ]
