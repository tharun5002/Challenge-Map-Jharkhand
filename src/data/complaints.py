"""Canonical complaint schema and validation for ChallengeMap datasets."""

from __future__ import annotations

from datetime import datetime
from math import isfinite

import pandas as pd


DISTRICTS = (
    "Bokaro",
    "Chatra",
    "Deoghar",
    "Dhanbad",
    "Dumka",
    "East Singhbhum",
    "Garhwa",
    "Giridih",
    "Godda",
    "Gumla",
    "Hazaribagh",
    "Jamtara",
    "Khunti",
    "Koderma",
    "Latehar",
    "Lohardaga",
    "Pakur",
    "Palamu",
    "Ramgarh",
    "Ranchi",
    "Sahibganj",
    "Seraikela-Kharsawan",
    "Simdega",
    "West Singhbhum",
)

COMPLAINT_COLUMNS = (
    "complaint_id",
    "complaint_text",
    "district",
    "block",
    "complaint_date",
    "language",
    "severity",
    "affected_population",
    "source_type",
    "verification_status",
)

SOURCE_TYPES = ("public_dataset", "consent_survey", "synthetic", "other")
SEVERITY_LEVELS = ("unknown", "low", "medium", "high", "critical")
VERIFICATION_STATUSES = (
    "unverified",
    "pending_review",
    "verified",
    "synthetic_not_verified",
)


def _is_missing(value: object) -> bool:
    return value is None or pd.isna(value) or (
        isinstance(value, str) and not value.strip()
    )


def _normalize_iso_date(value: object, row_number: int) -> str | pd.NA:
    if _is_missing(value):
        return pd.NA
    try:
        return datetime.fromisoformat(str(value).strip()).date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"Row {row_number}: complaint_date must be an ISO date "
            "(YYYY-MM-DD) or empty."
        ) from error


def _normalize_population(value: object, row_number: int) -> int | pd.NA:
    if _is_missing(value):
        return pd.NA
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Row {row_number}: affected_population must be a non-negative "
            "whole number or empty."
        ) from error
    if not isfinite(numeric_value) or numeric_value < 0 or not numeric_value.is_integer():
        raise ValueError(
            f"Row {row_number}: affected_population must be a non-negative "
            "whole number or empty."
        )
    return int(numeric_value)


def prepare_complaints(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize complaint rows without inventing missing facts."""
    required = {"complaint_id", "complaint_text", "district"}
    missing_columns = sorted(required.difference(frame.columns))
    if missing_columns:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing_columns)
        )

    working = frame.copy()
    for column in COMPLAINT_COLUMNS:
        if column not in working:
            working[column] = pd.NA

    for column in ("complaint_id", "complaint_text", "district"):
        working[column] = working[column].fillna("").astype(str).str.strip()
        empty_rows = (working[column] == "").to_numpy().nonzero()[0]
        if len(empty_rows):
            row_numbers = ", ".join(str(index + 2) for index in empty_rows[:10])
            raise ValueError(
                f"Required field '{column}' is empty on CSV row(s): {row_numbers}."
            )

    duplicate_ids = working.loc[
        working["complaint_id"].duplicated(keep=False), "complaint_id"
    ].unique()
    if len(duplicate_ids):
        raise ValueError(
            "complaint_id values must be unique. Duplicates: "
            + ", ".join(map(str, duplicate_ids[:10]))
        )

    district_lookup = {name.casefold(): name for name in DISTRICTS}
    normalized_districts = working["district"].str.casefold().map(district_lookup)
    if normalized_districts.isna().any():
        unknown = sorted(working.loc[normalized_districts.isna(), "district"].unique())
        raise ValueError(
            "Unknown Jharkhand district name(s): "
            + ", ".join(unknown[:10])
            + ". Use one of the 24 district names in the data guide."
        )
    working["district"] = normalized_districts

    working["block"] = working["block"].map(
        lambda value: pd.NA if _is_missing(value) else str(value).strip()
    ).astype("string")
    working["complaint_date"] = pd.Series(
        [
            _normalize_iso_date(value, row_number)
            for row_number, value in enumerate(working["complaint_date"], start=2)
        ],
        index=working.index,
        dtype="string",
    )
    working["language"] = working["language"].map(
        lambda value: "unknown" if _is_missing(value) else str(value).strip()
    ).astype("string")

    working["severity"] = working["severity"].map(
        lambda value: "unknown" if _is_missing(value) else str(value).strip().lower()
    )
    invalid_severity = ~working["severity"].isin(SEVERITY_LEVELS)
    if invalid_severity.any():
        invalid_values = sorted(working.loc[invalid_severity, "severity"].unique())
        raise ValueError(
            "Invalid severity value(s): "
            + ", ".join(invalid_values)
            + ". Allowed values: "
            + ", ".join(SEVERITY_LEVELS)
        )

    working["affected_population"] = pd.Series(
        [
            _normalize_population(value, row_number)
            for row_number, value in enumerate(
                working["affected_population"], start=2
            )
        ],
        index=working.index,
        dtype="Int64",
    )

    working["source_type"] = working["source_type"].map(
        lambda value: "other" if _is_missing(value) else str(value).strip().lower()
    )
    invalid_sources = ~working["source_type"].isin(SOURCE_TYPES)
    if invalid_sources.any():
        invalid_values = sorted(working.loc[invalid_sources, "source_type"].unique())
        raise ValueError(
            "Invalid source_type value(s): "
            + ", ".join(invalid_values)
            + ". Allowed values: "
            + ", ".join(SOURCE_TYPES)
        )

    provided_status = working["verification_status"].map(
        lambda value: (
            "" if _is_missing(value) else str(value).strip().lower()
        )
    )
    explicitly_verified_synthetic = (
        working["source_type"].eq("synthetic") & provided_status.eq("verified")
    )
    if explicitly_verified_synthetic.any():
        raise ValueError("Synthetic records cannot be marked verified.")

    working["verification_status"] = provided_status
    working.loc[
        working["verification_status"].eq(""),
        "verification_status",
    ] = "unverified"
    working.loc[
        working["source_type"].eq("synthetic"),
        "verification_status",
    ] = "synthetic_not_verified"

    invalid_statuses = ~working["verification_status"].isin(VERIFICATION_STATUSES)
    if invalid_statuses.any():
        invalid_values = sorted(
            working.loc[invalid_statuses, "verification_status"].unique()
        )
        raise ValueError(
            "Invalid verification_status value(s): "
            + ", ".join(invalid_values)
            + ". Allowed values: "
            + ", ".join(VERIFICATION_STATUSES)
        )

    verified_synthetic = (
        working["source_type"].eq("synthetic")
        & working["verification_status"].eq("verified")
    )
    if verified_synthetic.any():
        raise ValueError("Synthetic records cannot be marked verified.")

    return working.loc[:, COMPLAINT_COLUMNS].reset_index(drop=True)


def convert_legacy_synthetic(frame: pd.DataFrame) -> pd.DataFrame:
    """Adapt the original 40-row sample and explicitly keep its synthetic label."""
    required = {"report_id", "district", "report_text"}
    missing_columns = sorted(required.difference(frame.columns))
    if missing_columns:
        raise ValueError(
            "Legacy sample is missing columns: " + ", ".join(missing_columns)
        )
    converted = pd.DataFrame(
        {
            "complaint_id": frame["report_id"],
            "complaint_text": frame["report_text"],
            "district": frame["district"],
            "block": pd.NA,
            "complaint_date": pd.NA,
            "language": "en",
            "severity": "unknown",
            "affected_population": pd.NA,
            "source_type": "synthetic",
            "verification_status": "synthetic_not_verified",
        }
    )
    return prepare_complaints(converted)
