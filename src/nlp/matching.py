"""Explainable partner matching (plan section 6.1, stage 7).

``0.40*tag_overlap + 0.25*district_proximity + 0.20*severity + 0.15*capacity``

The score is never returned alone. Every match carries the component values and
their weighted contributions, because the interface promises sentences like
"Civil Engineering, BIT Mesra - 0.82 (water-infrastructure x3, 2 districts within
60 km, 14,000 affected)".

District proximity is exact-district by default: 1.0 when the partner works in a
district the challenge touches, otherwise 0.0. Pass ``distance_km`` to use real
geography instead; the default exists because the project has no validated
district-centroid table yet, and inventing distances would be worse than
declaring the simplification.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

WEIGHT_NAMES = ("tag_overlap", "district_proximity", "severity", "capacity")
DEFAULT_WEIGHTS: dict[str, float] = {
    "tag_overlap": 0.40,
    "district_proximity": 0.25,
    "severity": 0.20,
    "capacity": 0.15,
}

# Distance decay used when ``distance_km`` is supplied: a partner 150 km away
# keeps ~37% of the proximity credit.
DISTANCE_SCALE_KM = 150.0


@dataclass(frozen=True)
class ChallengeProfile:
    challenge_id: str
    capability_tags: frozenset[str]
    districts: frozenset[str]
    severity_score: float


@dataclass(frozen=True)
class PartnerProfile:
    organization_id: str
    name: str
    capability_tags: frozenset[str]
    districts: frozenset[str]
    capacity: float


def validate_weights(weights: Mapping[str, float]) -> dict[str, float]:
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
    if path is None:
        return dict(DEFAULT_WEIGHTS)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_weights(payload.get("weights", payload))


def _clamp(value: float) -> float:
    return float(min(max(value, 0.0), 1.0))


def score_match(
    challenge: ChallengeProfile,
    partner: PartnerProfile,
    *,
    weights: Mapping[str, float] | None = None,
    distance_km: float | None = None,
) -> dict[str, object]:
    """Score one partner against one challenge and explain the score."""
    resolved = validate_weights(weights or DEFAULT_WEIGHTS)

    challenge_tags = {tag.casefold() for tag in challenge.capability_tags}
    partner_tags = {tag.casefold() for tag in partner.capability_tags}
    tag_overlap = (
        len(challenge_tags & partner_tags) / len(challenge_tags) if challenge_tags else 0.0
    )

    shared_districts = {name.casefold() for name in challenge.districts} & {
        name.casefold() for name in partner.districts
    }
    if shared_districts:
        proximity = 1.0
    elif distance_km is not None:
        proximity = math.exp(-max(float(distance_km), 0.0) / DISTANCE_SCALE_KM)
    else:
        proximity = 0.0

    components = {
        "tag_overlap": _clamp(tag_overlap),
        "district_proximity": _clamp(proximity),
        "severity": _clamp(float(challenge.severity_score)),
        "capacity": _clamp(float(partner.capacity)),
    }
    weighted = {name: round(resolved[name] * value, 4) for name, value in components.items()}
    score = round(sum(weighted.values()), 4)
    return {
        "organization_id": partner.organization_id,
        "name": partner.name,
        "score": score,
        "components": {name: round(value, 4) for name, value in components.items()},
        "weighted": weighted,
        "weights": dict(resolved),
    }


def rank_matches(
    challenge: ChallengeProfile,
    partners: Sequence[PartnerProfile],
    *,
    weights: Mapping[str, float] | None = None,
    top_k: int | None = None,
    distances_km: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Rank candidate partners for a challenge, best first."""
    if top_k is not None and top_k < 1:
        raise ValueError("top_k must be at least 1")
    rows = []
    for partner in partners:
        distance = None if distances_km is None else distances_km.get(partner.organization_id)
        rows.append(
            score_match(
                challenge, partner, weights=weights, distance_km=distance
            )
        )
    if not rows:
        return pd.DataFrame(
            columns=["organization_id", "name", "score", "breakdown"]
        )

    frame = pd.DataFrame(rows)
    frame["breakdown"] = [
        {
            "components": row["components"],
            "weighted": row["weighted"],
            "weights": row["weights"],
        }
        for row in rows
    ]
    frame = frame.sort_values(
        ["score", "organization_id"], ascending=[False, True]
    ).reset_index(drop=True)
    if top_k is not None:
        frame = frame.head(top_k)
    return frame[["organization_id", "name", "score", "breakdown"]]
