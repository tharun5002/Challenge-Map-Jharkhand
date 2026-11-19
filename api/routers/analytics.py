"""Public analytics over submitted complaints.

Only real submitted rows are counted here: no synthetic corpus rows are loaded
into this database, so a district count is a count of reports the API actually
received. That is a much smaller number than the demo UI shows, and it should be.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import DistrictStat, TrendPoint
from api.store import connection
from src.data.complaints import DISTRICTS

router = APIRouter(prefix="/analytics", tags=["analytics"])

SEVERITY_SCORE = (
    "CASE severity "
    "WHEN 'low' THEN 0.25 WHEN 'medium' THEN 0.5 "
    "WHEN 'high' THEN 0.75 WHEN 'critical' THEN 1.0 ELSE 0.0 END"
)


@router.get("/districts", response_model=list[DistrictStat])
def district_counts() -> list[DistrictStat]:
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT district, COUNT(*) AS complaints, AVG({SEVERITY_SCORE}) AS severity_mean
            FROM complaints
            GROUP BY district
            """
        ).fetchall()
    measured = {row["district"]: row for row in rows}
    result: list[DistrictStat] = []
    for district in DISTRICTS:
        row = measured.get(district)
        result.append(
            DistrictStat(
                district=district,
                complaints=int(row["complaints"]) if row else 0,
                severity_mean=round(float(row["severity_mean"] or 0.0), 4) if row else 0.0,
            )
        )
    return result


@router.get("/trends", response_model=list[TrendPoint])
def trends() -> list[TrendPoint]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(c.reported_on, 1, 7) AS month,
                   COALESCE(ch.domain, 'unassigned') AS domain,
                   COUNT(*) AS complaints
            FROM complaints c
            LEFT JOIN challenge_complaints cc ON cc.complaint_report_id = c.report_id
            LEFT JOIN challenges ch ON ch.id = cc.challenge_id
            GROUP BY month, domain
            ORDER BY month, domain
            """
        ).fetchall()
    return [
        TrendPoint(
            month=row["month"],
            domain=row["domain"],
            complaints=int(row["complaints"]),
        )
        for row in rows
    ]
