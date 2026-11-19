"""Semantic complaint-pair candidates for human duplicate review."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.nlp.embeddings import SentenceEncoder, encode_complaints
from src.nlp.text_preparation import normalize_complaint_text


DUPLICATE_CANDIDATE_COLUMNS = (
    "complaint_id",
    "similar_complaint_id",
    "similarity",
    "complaint_text",
    "similar_complaint_text",
    "review_status",
)


def find_duplicate_candidates(
    complaint_ids: Sequence[object],
    complaint_texts: Sequence[object],
    embeddings: np.ndarray,
    *,
    similarity_threshold: float = 0.85,
) -> pd.DataFrame:
    """Return unique, thresholded similarity pairs without labeling truth."""
    ids = [
        ""
        if complaint_id is None or pd.isna(complaint_id)
        else str(complaint_id).strip()
        for complaint_id in complaint_ids
    ]
    texts = [normalize_complaint_text(text) for text in complaint_texts]
    if len(ids) < 2:
        raise ValueError("At least two complaints are required.")
    if len(ids) != len(texts):
        raise ValueError("Complaint IDs and texts must have the same length.")
    if any(not complaint_id for complaint_id in ids):
        raise ValueError("Complaint IDs must not be empty.")
    if len(set(ids)) != len(ids):
        raise ValueError("Complaint IDs must be unique.")
    if any(not text for text in texts):
        raise ValueError("Complaint texts must not contain empty values.")
    if (
        isinstance(similarity_threshold, bool)
        or not isinstance(similarity_threshold, (int, float))
        or not 0 <= similarity_threshold <= 1
    ):
        raise ValueError("similarity_threshold must be between 0 and 1.")

    vectors = np.asarray(embeddings, dtype=np.float32)
    if (
        vectors.ndim != 2
        or vectors.shape[0] != len(ids)
        or vectors.shape[1] == 0
    ):
        raise ValueError("Embeddings must have one non-empty vector per complaint.")
    if not np.isfinite(vectors).all():
        raise ValueError("Embeddings must contain only finite values.")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0):
        raise ValueError("Embeddings must not contain zero-length vectors.")

    unit_vectors = vectors / norms[:, np.newaxis]
    candidates: list[dict[str, object]] = []
    for left_index in range(len(ids) - 1):
        similarities = unit_vectors[left_index + 1 :] @ unit_vectors[left_index]
        for offset in np.flatnonzero(similarities >= similarity_threshold):
            right_index = left_index + 1 + int(offset)
            candidates.append(
                {
                    "complaint_id": ids[left_index],
                    "similar_complaint_id": ids[right_index],
                    "similarity": float(similarities[offset]),
                    "complaint_text": texts[left_index],
                    "similar_complaint_text": texts[right_index],
                    "review_status": "pending_review",
                }
            )

    if not candidates:
        return pd.DataFrame(columns=DUPLICATE_CANDIDATE_COLUMNS)

    return (
        pd.DataFrame(candidates, columns=DUPLICATE_CANDIDATE_COLUMNS)
        .sort_values(
            ["similarity", "complaint_id", "similar_complaint_id"],
            ascending=[False, True, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def detect_duplicate_candidates(
    complaint_ids: Sequence[object],
    complaint_texts: Sequence[object],
    encoder: SentenceEncoder,
    *,
    similarity_threshold: float = 0.85,
    batch_size: int = 32,
) -> pd.DataFrame:
    """Encode complaint text and return pairs needing human review."""
    embeddings = encode_complaints(
        encoder,
        complaint_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
    )
    return find_duplicate_candidates(
        complaint_ids,
        complaint_texts,
        embeddings,
        similarity_threshold=similarity_threshold,
    )
