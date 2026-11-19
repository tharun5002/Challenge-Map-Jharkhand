"""Transparent priority index for complaint groups (plan section 6.1, stage 6).

``0.30*severity + 0.25*log(affected) + 0.20*volume + 0.15*district_spread
+ 0.10*recurrence``

Every component is normalised to 0..1 across the groups being scored, then
weighted, so the final score is 0..100. The breakdown is stored next to the
score: a priority number nobody can explain is worthless in a civic product.

Definitions, because they matter:

* ``recurrence`` — share of a group's reports whose normalised text was already
  reported in that group. This is "the same problem reported again", not
  "recent activity"; recency would need a scoring date and is not part of it.
* ``affected_population`` — log1p of the summed affected population. Log because
  a 100,000-person outage is not a thousand times worse than a 100-person one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from src.nlp.text_preparation import prepare_text_for_tfidf

WEIGHT_NAMES = ("severity", "affected_population", "volume", "district_spread", "recurrence")
DEFAULT_WEIGHTS: dict[str, float] = {
    "severity": 0.30,
    "affected_population": 0.25,
    "volume": 0.20,
    "district_spread": 0.15,
    "recurrence": 0.10,
}
SEVERITY_SCORES: dict[str, float] = {
    "unknown": 0.0,
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}
COMPONENT_COLUMNS: dict[str, str] = {
    "severity": "severity_component",
    "affected_population": "affected_component",
    "volume": "volume_component",
    "district_spread": "district_spread_component",
    "recurrence": "recurrence_component",
}


def validate_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Check that the five weights exist, are non-negative and sum to one."""
    missing = [name for name in WEIGHT_NAMES if name not in weights]
    unknown = [name for name in weights if name not in WEIGHT_NAMES]
    if missing:
        raise ValueError("Missing weight(s): " + ", ".join(missing))
    if unknown:
        raise ValueError("Unknown weight(s): " + ", ".join(unknown))
    values = np.array([float(weights[name]) for name in WEIGHT_NAMES])
    if np.any(values < 0):
        raise ValueError("weights must be non-negative")
    if not np.isclose(values.sum(), 1.0, atol=1e-6):
        raise ValueError(f"weights must sum to 1.0, got {values.sum():.4f}")
    return {name: float(weights[name]) for name in WEIGHT_NAMES}


def load_weights(path: str | Path | None = None) -> dict[str, float]:
    """Load weights from ``models/priority_weights.json`` or return the defaults."""
    if path is None:
        return dict(DEFAULT_WEIGHTS)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    weights = payload.get("weights", payload)
    return validate_weights(weights)


def _scale(values: pd.Series) -> pd.Series:
    """Divide by the largest value so the component fills 0..1."""
    maximum = float(values.max()) if len(values) else 0.0
    if maximum <= 0:
        return pd.Series(0.0, index=values.index)
    return values / maximum


def score_priorities(
    complaints: pd.DataFrame,
    *,
    group_column: str = "challenge_id",
    weights: Mapping[str, float] | None = None,
    district_count: int = 24,
) -> pd.DataFrame:
    """Score each complaint group and return its component breakdown."""
    resolved = validate_weights(weights or DEFAULT_WEIGHTS)
    required = {group_column, "severity", "affected_population", "district", "complaint_text"}
    missing = sorted(required.difference(complaints.columns))
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(missing))
    if complaints.empty:
        raise ValueError("no complaints to score")
    if district_count <= 0:
        raise ValueError("district_count must be positive")

    frame = complaints.copy()
    frame["_severity"] = (
        frame["severity"].astype(str).str.strip().str.lower().map(SEVERITY_SCORES).fillna(0.0)
    )
    frame["_population"] = pd.to_numeric(
        frame["affected_population"], errors="coerce"
    ).fillna(0.0)
    frame["_text"] = [prepare_text_for_tfidf(text) for text in frame["complaint_text"]]
    frame["_repeated"] = frame.duplicated(subset=[group_column, "_text"], keep="first")

    grouped = frame.groupby(group_column, dropna=False)
    summary = pd.DataFrame(
        {
            "complaint_count": grouped.size(),
            "affected_total": grouped["_population"].sum(),
            "district_count": grouped["district"].nunique(),
            "severity_mean": grouped["_severity"].mean(),
            "recurrence_rate": grouped["_repeated"].mean(),
        }
    )

    summary["severity_component"] = summary["severity_mean"].clip(lower=0.0, upper=1.0)
    summary["affected_component"] = _scale(np.log1p(summary["affected_total"]))
    summary["volume_component"] = _scale(np.log1p(summary["complaint_count"]))
    summary["district_spread_component"] = (summary["district_count"] / district_count).clip(
        upper=1.0
    )
    summary["recurrence_component"] = summary["recurrence_rate"].clip(lower=0.0, upper=1.0)

    score = np.zeros(len(summary), dtype=np.float64)
    for name, column in COMPONENT_COLUMNS.items():
        score += resolved[name] * summary[column].to_numpy(dtype=np.float64)
    summary["priority_score"] = np.round(score * 100.0, 2)

    summary["priority_breakdown"] = [
        {
            **{
                name: round(float(summary.iloc[row][column]), 4)
                for name, column in COMPONENT_COLUMNS.items()
            },
            "weights": dict(resolved),
        }
        for row in range(len(summary))
    ]

    result = summary.reset_index()
    return result.sort_values(
        ["priority_score", group_column], ascending=[False, True]
    ).reset_index(drop=True)
