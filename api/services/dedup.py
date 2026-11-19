"""Duplicate candidates for a freshly submitted complaint.

The index is the complaints table, not the 15k synthetic corpus: a submitter
should see reports the system actually holds. A district block keeps this linear
until Phase 2's pgvector index replaces it.

Similarity is the exact sparse TF-IDF cosine measured in Phase 4 (best F1 0.743
at threshold 0.85 on the synthetic corpus). The default threshold here is 0.86,
matching `.env.example`, because the product shows candidates for a human to
decide on; it does not auto-merge.
"""

from __future__ import annotations

import numpy as np

from api.store import connection
from src.nlp.vectorizers import TfidfEncoder

MAX_BLOCK = 500


def duplicate_candidates(
    report_id: str,
    district: str,
    raw_text: str,
    *,
    threshold: float,
    limit: int = 5,
) -> list[dict[str, object]]:
    with connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT report_id, raw_text, district
                FROM complaints
                WHERE district = ? AND report_id <> ? AND status <> 'merged'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (district, report_id, MAX_BLOCK),
            ).fetchall()
        ]
    if not rows:
        return []

    texts = [raw_text] + [str(row["raw_text"]) for row in rows]
    encoder = TfidfEncoder(analyzer="word", ngram_range=(1, 2), min_df=1)
    try:
        encoder.fit(texts)
        matrix = encoder.encode_sparse(texts)
    except (ValueError, RuntimeError):
        return []

    scores = np.asarray((matrix[0] @ matrix[1:].T).todense(), dtype=np.float32).ravel()
    candidates: list[dict[str, object]] = []
    for index in np.argsort(-scores)[:limit]:
        similarity = float(scores[index])
        if similarity < threshold:
            break
        candidates.append(
            {
                "report_id": rows[index]["report_id"],
                "similarity": round(similarity, 4),
                "district": rows[index]["district"],
                "report_text": rows[index]["raw_text"],
            }
        )
    return candidates
