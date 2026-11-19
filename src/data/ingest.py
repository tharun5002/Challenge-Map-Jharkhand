"""Ingestion adapters: bring any complaint source onto the canonical schema.

The point of this module is that swapping synthetic data for a real extract is a
configuration change, not a rewrite. Each adapter maps its source columns onto the
canonical names in ``src/data/complaints.py``, scrubs direct identifiers, and
refuses to proceed without an explicit source type.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.data.complaints import SOURCE_TYPES, prepare_complaints

# Direct identifiers. Deliberately conservative: false positives are cheaper than
# publishing a phone number next to a complaint.
PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "[email]"),
    (re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b"), "[phone]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[id-number]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[pan]"),
)

# Canonical column -> accepted source column names, checked case-insensitively.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "complaint_id": (
        "complaint_id",
        "id",
        "grievance_id",
        "complaint_no",
        "acknowledgement_no",
        "registration_no",
    ),
    "complaint_text": (
        "complaint_text",
        "text",
        "description",
        "subject_content",
        "complaint",
        "grievance",
        "remarks",
    ),
    "district": ("district", "district_name", "districtname"),
    "block": ("block", "block_name", "taluka"),
    "complaint_date": ("complaint_date", "date", "diarydate", "created_date", "reported_on"),
    "language": ("language", "lang"),
    "severity": ("severity", "priority"),
    "affected_population": ("affected_population", "population_affected", "affected"),
}

REQUIRED_CANONICAL = ("complaint_id", "complaint_text", "district")


def _column_key(value: object) -> str:
    """Normalise a header so 'District Name' matches the alias 'district_name'."""
    return re.sub(r"[\s_-]+", "_", str(value).strip().casefold())


def scrub_pii(text: str) -> str:
    """Replace phone numbers, emails and long numeric identifiers."""
    cleaned = text
    for pattern, replacement in PII_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def resolve_columns(frame: pd.DataFrame, column_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Rename source columns to canonical names.

    ``column_map`` is explicit (source name -> canonical name) and always wins.
    Otherwise aliases are matched case-insensitively.
    """
    working = frame.copy()
    if column_map:
        missing = set(column_map.values()) - set(working.columns)
        unknown_targets = missing - set(COLUMN_ALIASES) - set(REQUIRED_CANONICAL) - {
            "source_type",
            "verification_status",
        }
        if unknown_targets:
            raise ValueError(
                "column_map targets unknown canonical fields: " + ", ".join(sorted(unknown_targets))
            )
        working = working.rename(
            columns={source: target for source, target in column_map.items()}
        )

    # After an explicit map is applied, any canonical field still missing is
    # resolved through the alias table, so a partial map behaves predictably.
    keyed_lookup = {_column_key(column): column for column in working.columns}
    rename: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in working.columns:
            continue
        for alias in aliases:
            source = keyed_lookup.get(_column_key(alias))
            if source is not None:
                rename[source] = canonical
                break
    return working.rename(columns=rename)


def ingest_frame(
    frame: pd.DataFrame,
    source_type: str,
    column_map: dict[str, str] | None = None,
    default_district: str | None = None,
) -> pd.DataFrame:
    """Prepare an arbitrary frame as canonical, unverified complaint rows."""
    if source_type not in SOURCE_TYPES:
        raise ValueError(
            f"Unknown source_type '{source_type}'. Allowed: {', '.join(SOURCE_TYPES)}"
        )

    working = resolve_columns(frame, column_map)
    missing = [column for column in REQUIRED_CANONICAL if column not in working.columns]
    if missing:
        raise ValueError(
            "Source is missing required column(s): "
            + ", ".join(missing)
            + ". Provide a column_map if the source uses different names."
        )

    if default_district and "district" in working.columns:
        working["district"] = working["district"].fillna(default_district)

    working["complaint_id"] = working["complaint_id"].astype(str).str.strip()
    working["complaint_text"] = (
        working["complaint_text"].astype(str).map(scrub_pii).str.strip()
    )
    working["source_type"] = source_type
    if "verification_status" not in working.columns:
        working["verification_status"] = "unverified"

    return prepare_complaints(working)


def ingest_csv(
    path: str | Path,
    source_type: str,
    column_map: dict[str, str] | None = None,
    default_district: str | None = None,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """Read a CSV and return canonical, PII-scrubbed complaint rows."""
    frame = pd.read_csv(Path(path), encoding=encoding)
    return ingest_frame(
        frame,
        source_type=source_type,
        column_map=column_map,
        default_district=default_district,
    )


# Ready-made mappings for the two shapes described in docs/MASTER_PLAN.md.
CPGRAMS_COLUMN_MAP: dict[str, str] = {
    "subject_content": "complaint_text",
    "diarydate": "complaint_date",
}

PGMS_COLUMN_MAP: dict[str, str] = {
    "complaint_no": "complaint_id",
    "complaint": "complaint_text",
    "district_name": "district",
    "complaint_date": "complaint_date",
}
